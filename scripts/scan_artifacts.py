#!/usr/bin/env python3
"""SessionStart hook: scan for artifact files and backfill the Context Library.

Runs ASYNC on SessionStart. Performs three tasks:
  1. Check tracked files in manifest — archive deleted, re-ingest changed
  2. Scan known directories for untracked artifacts — classify and ingest new
  3. Write updated manifest

Uses only stdlib. Always exits 0.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.artifact_patterns import classify_file  # type: ignore[import]
from lib.config import get_api_url, get_frontend_url  # type: ignore[import]
from lib.auth import resolve_auth_headers  # type: ignore[import]
from lib.hook_log import log_hook_issue  # type: ignore[import]
from lib.manifest import (  # type: ignore[import]
    content_hash,
    file_hash,
    get_entry,
    read_manifest,
    remove_entry,
    set_entry,
    to_relative,
    write_manifest,
)

# Directories to scan for untracked artifacts (relative to cwd)
_SCAN_DIRS = ["docs", "specs", "plans"]


def _api_request(method: str, path: str, payload: dict | None = None) -> dict | None:
    """Make an API request. Returns response dict or None."""
    from urllib import request as urllib_request
    from urllib.error import HTTPError, URLError

    api_url = get_api_url()
    auth_headers = resolve_auth_headers()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "vibecheck-plugin/scan-artifacts",
        **auth_headers,
    }

    data = json.dumps(payload, default=str).encode() if payload else None
    try:
        req = urllib_request.Request(
            f"{api_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib_request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else None
    except (HTTPError, URLError, OSError, Exception) as e:
        log_hook_issue("scan_artifacts", f"{method} {path} failed", e)
        return None


def _archive_context(context_id: str) -> bool:
    """Archive a context by ID."""
    resp = _api_request("POST", f"/api/contexts/{context_id}/status", {
        "status": "archived",
        "evidence": {"reason": "source_file_deleted", "scanner": "scan_artifacts"},
    })
    return resp is not None


def _create_context(file_path: str, content: str, context_type: str, session_id: str) -> dict | None:
    """Create a new context from a file."""
    import re

    # Extract title
    match = re.search(r"^#{1,6}\s+(.+)", content, re.MULTILINE)
    title = match.group(1).strip()[:200] if match else os.path.splitext(os.path.basename(file_path))[0].replace("-", " ").replace("_", " ").title()

    from datetime import datetime, timezone
    return _api_request("POST", "/api/contexts", {
        "title": title,
        "type": context_type,
        "brief": content,
        "tags": ["auto-captured", "backfill"],
        "source_type": "artifact_capture",
        "source_ref": file_path,
        "source_snapshot": {
            "file_path": file_path,
            "file_hash": content_hash(content),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        },
        "created_by": "system",
    })


def _update_context(context_id: str, file_path: str, content: str, session_id: str) -> dict | None:
    """Update an existing context with new content."""
    import re
    from datetime import datetime, timezone

    match = re.search(r"^#{1,6}\s+(.+)", content, re.MULTILINE)
    title = match.group(1).strip()[:200] if match else None

    payload: dict = {
        "brief": content,
        "source_snapshot": {
            "file_path": file_path,
            "file_hash": content_hash(content),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        },
    }
    if title:
        payload["title"] = title

    return _api_request("PATCH", f"/api/contexts/{context_id}", payload)


def _walk_for_artifacts(cwd: str, manifest: dict) -> list[tuple[str, str, str, str]]:
    """Walk scan directories for untracked markdown files.

    Returns list of (rel_path, abs_path, content, context_type) for new artifacts.
    """
    results = []
    tracked = set(manifest.get("artifacts", {}).keys())

    for scan_dir in _SCAN_DIRS:
        abs_dir = os.path.join(cwd, scan_dir)
        if not os.path.isdir(abs_dir):
            continue
        for root, _dirs, files in os.walk(abs_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                abs_path = os.path.join(root, fname)
                rel_path = to_relative(abs_path, cwd)
                if rel_path in tracked:
                    continue
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue
                classification = classify_file(rel_path, content)
                if classification:
                    ctx_type, _confidence = classification
                    results.append((rel_path, abs_path, content, ctx_type))

    return results


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception as e:
        log_hook_issue("scan_artifacts", "Failed to parse hook payload", e)
        sys.exit(0)

    cwd = hook_data.get("cwd", os.getcwd())
    session_id = hook_data.get("session_id", "unknown")

    manifest = read_manifest(cwd)
    artifacts = manifest.get("artifacts", {})
    changed = False

    # Phase 1: Check tracked files
    for rel_path in list(artifacts.keys()):
        entry = artifacts[rel_path]
        abs_path = os.path.join(cwd, rel_path)

        if not os.path.exists(abs_path):
            # File deleted — archive context
            context_id = entry.get("context_id", "")
            if context_id:
                _archive_context(context_id)
            remove_entry(manifest, rel_path)
            changed = True
            continue

        # Check for content change
        current_hash = file_hash(abs_path)
        if current_hash and current_hash != entry.get("captured_hash"):
            # Content changed — re-ingest
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            context_id = entry.get("context_id", "")
            resp = _update_context(context_id, abs_path, content, session_id)
            if resp:
                label = resp.get("label", entry.get("context_label", ""))
                ctx_type = entry.get("context_type", "note")
                set_entry(manifest, rel_path, context_id, label, current_hash, ctx_type, session_id)
                changed = True

    # Phase 2: Scan for new untracked artifacts
    new_artifacts = _walk_for_artifacts(cwd, manifest)
    for rel_path, abs_path, content, ctx_type in new_artifacts:
        resp = _create_context(abs_path, content, ctx_type, session_id)
        if resp:
            context_id = resp.get("id", "")
            label = resp.get("label", "")
            h = content_hash(content)
            set_entry(manifest, rel_path, context_id, label, h, ctx_type, session_id)
            changed = True

    # Phase 3: Write manifest if changed
    if changed:
        write_manifest(cwd, manifest)


if __name__ == "__main__":
    main()
