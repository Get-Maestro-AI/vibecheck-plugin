#!/usr/bin/env python3
"""SessionStart hook: auto-index local skills from ~/.claude/commands/.

Scans ~/.claude/commands/**/*.md for skill files, parses frontmatter for
description, and creates/updates Context Library entries as type=skill.

Read-only on the filesystem — only writes to the Context Library API.
Skips the vibecheck/ subdirectory (already in the library).

Runs ASYNC on SessionStart. Uses only stdlib. Always exits 0.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.config import get_api_url  # type: ignore[import]
from lib.auth import resolve_auth_headers  # type: ignore[import]
from lib.hook_log import log_hook_issue  # type: ignore[import]
from lib.manifest import content_hash  # type: ignore[import]

# Index manifest: tracks which local skills have been indexed and their hashes.
_INDEX_FILE = Path.home() / ".vibecheck" / "skill-index.json"

# Directories to skip (already managed by VibeCheck)
_SKIP_DIRS = {"vibecheck"}


def _read_index() -> dict:
    """Read the skill index. Returns {file_path: {context_id, label, hash}}."""
    try:
        if _INDEX_FILE.exists():
            with open(_INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _write_index(index: dict) -> None:
    """Write the skill index atomically."""
    tmp = None
    try:
        _INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=str(_INDEX_FILE.parent), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, default=str)
            f.write("\n")
        os.replace(tmp, str(_INDEX_FILE))
    except Exception as e:
        log_hook_issue("index_skills", "Failed to write skill index", e)
        if tmp:
            try:
                os.unlink(tmp)
            except Exception:
                pass


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML-like frontmatter from markdown content.

    Returns dict with parsed key-value pairs. Handles the simple case of
    `key: value` lines between --- fences.
    """
    result = {}
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return result
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^(\w+):\s*(.+)$", line)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def _extract_summary(content: str, frontmatter: dict) -> str:
    """Extract a summary for the skill. Prefers frontmatter description."""
    desc = frontmatter.get("description", "")
    if desc:
        return desc[:500]

    # Fallback: first non-heading, non-empty paragraph
    lines = content.split("\n")
    in_frontmatter = False
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if not stripped or stripped.startswith("#"):
            continue
        return stripped[:500]

    return ""


def _api_request(method: str, path: str, payload: dict | None = None) -> dict | None:
    """Make an API request. Returns response dict or None."""
    from urllib import request as urllib_request
    from urllib.error import HTTPError, URLError

    api_url = get_api_url()
    auth_headers = resolve_auth_headers()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "vibecheck-plugin/index-skills",
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
        log_hook_issue("index_skills", f"{method} {path} failed", e)
        return None


def _scan_commands() -> list[tuple[str, str, dict]]:
    """Scan ~/.claude/commands/ for skill files.

    Returns list of (abs_path, content, frontmatter) for each .md file.
    """
    commands_dir = Path.home() / ".claude" / "commands"
    if not commands_dir.is_dir():
        return []

    results = []
    for root, dirs, files in os.walk(commands_dir):
        # Skip VibeCheck's own commands
        rel = os.path.relpath(root, commands_dir)
        top_dir = rel.split(os.sep)[0] if rel != "." else ""
        if top_dir in _SKIP_DIRS:
            continue

        for fname in files:
            if not fname.endswith(".md"):
                continue
            abs_path = os.path.join(root, fname)
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            frontmatter = _parse_frontmatter(content)
            results.append((abs_path, content, frontmatter))

    return results


def main() -> None:
    try:
        json.load(sys.stdin)  # consume stdin (required by hook protocol)
    except Exception:
        pass

    index = _read_index()
    changed = False
    seen_paths: set[str] = set()

    for abs_path, content, frontmatter in _scan_commands():
        seen_paths.add(abs_path)
        h = content_hash(content)

        existing = index.get(abs_path)
        if existing and existing.get("hash") == h:
            # Unchanged — skip
            continue

        summary = _extract_summary(content, frontmatter)
        if not summary:
            continue

        # Derive title from filename
        basename = os.path.basename(abs_path)
        name = os.path.splitext(basename)[0]
        # Include parent dir as namespace if not top-level
        commands_dir = str(Path.home() / ".claude" / "commands")
        rel = os.path.relpath(abs_path, commands_dir)
        parts = rel.replace("\\", "/").split("/")
        if len(parts) > 1:
            namespace = parts[0]
            title = f"{namespace}/{name}"
        else:
            title = name

        if existing:
            # Update existing context
            context_id = existing["context_id"]
            resp = _api_request("PATCH", f"/api/contexts/{context_id}", {
                "title": title,
                "brief": content,
                "context_summary": summary,
                "source_snapshot": {"file_path": abs_path, "file_hash": h},
            })
            if resp:
                index[abs_path] = {
                    "context_id": context_id,
                    "label": resp.get("label", existing.get("label", "")),
                    "hash": h,
                }
                changed = True
        else:
            # Create new skill context
            resp = _api_request("POST", "/api/contexts", {
                "title": title,
                "type": "skill",
                "brief": content,
                "context_summary": summary,
                "tags": ["auto-indexed", "local-command"],
                "source_type": "local_command",
                "source_ref": abs_path,
                "created_by": "system",
            })
            if resp:
                index[abs_path] = {
                    "context_id": resp.get("id", ""),
                    "label": resp.get("label", ""),
                    "hash": h,
                }
                changed = True

    # Clean up: remove entries for deleted files
    for path in list(index.keys()):
        if path not in seen_paths:
            # File was deleted — archive the context
            context_id = index[path].get("context_id", "")
            if context_id:
                _api_request("POST", f"/api/contexts/{context_id}/status", {
                    "status": "archived",
                    "evidence": {"reason": "source_file_deleted", "scanner": "index_skills"},
                })
            del index[path]
            changed = True

    if changed:
        _write_index(index)


if __name__ == "__main__":
    main()
