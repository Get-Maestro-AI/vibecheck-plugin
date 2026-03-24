#!/usr/bin/env python3
"""PostToolUse hook: capture artifact file writes into the Context Library.

Fires on Write and Edit tool uses. Classifies the file path, checks the
manifest for duplicates, and creates/updates a Context Library entry.

Runs SYNCHRONOUSLY so stdout is visible in the CLI conversation.
Non-matching files exit immediately (<10ms). Matching files complete in <500ms.

Uses only stdlib. Always exits 0.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add lib/ to path
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
    set_entry,
    to_relative,
    write_manifest,
)


def _extract_title(content: str, file_path: str) -> str:
    """Extract title from first markdown heading, fallback to filename."""
    match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    if match:
        title = match.group(1).strip()
        # Remove markdown formatting
        title = re.sub(r"[*_`]", "", title)
        if title:
            return title[:200]  # Cap length
    # Fallback: filename without extension, hyphen to space, title case
    basename = os.path.basename(file_path)
    name = os.path.splitext(basename)[0]
    return name.replace("-", " ").replace("_", " ").title()


def _get_content(hook_data: dict) -> tuple[str, str] | None:
    """Extract file_path and content from hook payload.

    For Write: content is in tool_input.content
    For Edit: read the file from disk (post-edit state)
    Returns (file_path, content) or None if not extractable.
    """
    tool_input = hook_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return None

    tool_name = hook_data.get("tool_name", "")

    if tool_name == "Write":
        content = tool_input.get("content", "")
        if content:
            return (file_path, content)
        # Write with no content — read from disk
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return (file_path, f.read())
        except Exception:
            return None

    elif tool_name == "Edit":
        # Edit only has old_string/new_string — read full file post-edit
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return (file_path, f.read())
        except Exception:
            return None

    return None


def _post_context(payload: dict) -> dict | None:
    """POST to /api/contexts. Returns response dict or None on failure."""
    from urllib import request as urllib_request
    from urllib.error import HTTPError, URLError

    api_url = get_api_url()
    auth_headers = resolve_auth_headers()

    data = json.dumps(payload, default=str).encode()
    try:
        req = urllib_request.Request(
            f"{api_url}/api/contexts",
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "vibecheck-plugin/capture-artifact",
                **auth_headers,
            },
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=4) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else None
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        log_hook_issue("capture_artifact", f"POST /api/contexts failed (status={e.code}, body={body})", e)
        return None
    except (URLError, OSError, Exception) as e:
        log_hook_issue("capture_artifact", "POST /api/contexts failed", e)
        return None


def _patch_context(context_id: str, payload: dict) -> dict | None:
    """PATCH an existing context. Returns response dict or None."""
    from urllib import request as urllib_request
    from urllib.error import HTTPError, URLError

    api_url = get_api_url()
    auth_headers = resolve_auth_headers()

    data = json.dumps(payload, default=str).encode()
    try:
        req = urllib_request.Request(
            f"{api_url}/api/contexts/{context_id}",
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "vibecheck-plugin/capture-artifact",
                **auth_headers,
            },
            method="PATCH",
        )
        with urllib_request.urlopen(req, timeout=4) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else None
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        log_hook_issue("capture_artifact", f"PATCH /api/contexts/{context_id} failed (status={e.code}, body={body})", e)
        return None
    except (URLError, OSError, Exception) as e:
        log_hook_issue("capture_artifact", f"PATCH /api/contexts/{context_id} failed", e)
        return None


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception as e:
        log_hook_issue("capture_artifact", "Failed to parse hook payload", e)
        sys.exit(0)

    try:
        _run(hook_data)
    except Exception as e:
        log_hook_issue("capture_artifact", "Unhandled error in capture hook", e)
        sys.exit(0)


def _run(hook_data: dict) -> None:
    """Core logic — separated so main() can catch all exceptions."""
    # Extract file path and content
    result = _get_content(hook_data)
    if not result:
        return

    file_path, content = result
    cwd = hook_data.get("cwd", os.getcwd())
    session_id = hook_data.get("session_id", "unknown")

    # Classify the file
    rel_path = to_relative(file_path, cwd)
    classification = classify_file(rel_path, content)
    if not classification:
        return

    context_type, confidence = classification

    # Use absolute path as manifest key for files outside the project tree
    # (e.g. ~/.claude/plans/). Relative paths with leading "../" are fragile
    # across sessions with different CWDs.
    manifest_key = file_path if rel_path.startswith("..") else rel_path

    # Check manifest
    manifest = read_manifest(cwd)
    entry = get_entry(manifest, manifest_key)
    current_hash = content_hash(content)
    now_iso = datetime.now(timezone.utc).isoformat()

    frontend_url = get_frontend_url()

    if entry:
        # Already tracked — check if content changed
        if entry.get("captured_hash") == current_hash:
            return

        # Content changed — update existing context
        context_id = entry.get("context_id", "")
        context_label = entry.get("context_label", "")
        if not context_id:
            return
        title = _extract_title(content, file_path)

        resp = _patch_context(context_id, {
            "brief": content,
            "title": title,
            "source_snapshot": {
                "file_path": file_path,
                "file_hash": current_hash,
                "captured_at": now_iso,
                "session_id": session_id,
            },
        })

        if resp:
            label = resp.get("label", context_label)
            set_entry(manifest, manifest_key, context_id, label, current_hash, context_type, session_id)
            write_manifest(cwd, manifest)
            print(f"\n[VibeCheck] Artifact updated: [{context_type}] \"{title}\" ({label})")
            print(f"  → {frontend_url}/#context/{label}\n")
        else:
            log_hook_issue("capture_artifact", f"Failed to update context {context_id} for {rel_path}")

    else:
        # New artifact — create context
        title = _extract_title(content, file_path)
        resp = _post_context({
            "title": title,
            "type": context_type,
            "brief": content,
            "tags": ["auto-captured"],
            "source_type": "artifact_capture",
            "source_ref": file_path,
            "source_snapshot": {
                "file_path": file_path,
                "file_hash": current_hash,
                "captured_at": now_iso,
                "session_id": session_id,
            },
            "created_by": "system",
        })

        if resp:
            context_id = resp.get("id", "")
            label = resp.get("label", "")
            set_entry(manifest, manifest_key, context_id, label, current_hash, context_type, session_id)
            write_manifest(cwd, manifest)
            print(f"\n[VibeCheck] Artifact captured: [{context_type}] \"{title}\" ({label})")
            print(f"  → {frontend_url}/#context/{label}\n")
        else:
            log_hook_issue("capture_artifact", f"Failed to create context for {rel_path}")


if __name__ == "__main__":
    main()
