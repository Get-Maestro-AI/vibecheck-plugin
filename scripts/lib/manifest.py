"""Artifact manifest: tracks file → context mappings with content hashes.

The manifest lives at ~/.vibecheck/{board_slug}/artifact-manifest.json (per-board,
user-global). Legacy location: <project>/.vibecheck/artifact-manifest.json.

Uses only stdlib. Never raises from public API — returns safe defaults on error.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_MANIFEST_VERSION = 1
_MANIFEST_DIR = ".vibecheck"
_MANIFEST_FILE = "artifact-manifest.json"
_VC_HOME = Path.home() / ".vibecheck"


def content_hash(content: str) -> str:
    """SHA-256 hash of content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def file_hash(file_path: str) -> str | None:
    """SHA-256 hash of a file's content. Returns None if unreadable."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return content_hash(f.read())
    except Exception:
        return None


def _manifest_path(cwd: str) -> Path:
    """Return the legacy manifest file path for a project directory."""
    return Path(cwd) / _MANIFEST_DIR / _MANIFEST_FILE


def _board_manifest_path(board_slug: str) -> Path:
    """Return the board-level manifest path: ~/.vibecheck/{board_slug}/artifact-manifest.json."""
    return _VC_HOME / board_slug / _MANIFEST_FILE


def read_manifest(cwd: str, board_slug: str | None = None) -> dict[str, Any]:
    """Read the manifest. Prefers board-level path if board_slug provided, else legacy."""
    try:
        mp = _board_manifest_path(board_slug) if board_slug else _manifest_path(cwd)
        if not mp.exists():
            return {"version": _MANIFEST_VERSION, "artifacts": {}}
        with open(mp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "artifacts" not in data:
            return {"version": _MANIFEST_VERSION, "artifacts": {}}
        return data
    except Exception:
        return {"version": _MANIFEST_VERSION, "artifacts": {}}


def write_manifest(cwd: str, manifest: dict[str, Any], board_slug: str | None = None) -> bool:
    """Write the manifest atomically. Uses board-level path if board_slug provided."""
    try:
        mp = _board_manifest_path(board_slug) if board_slug else _manifest_path(cwd)
        mp.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp file in same dir, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(mp.parent), suffix=".tmp", prefix="manifest-"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, default=str)
                f.write("\n")
            os.replace(tmp_path, str(mp))
            return True
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return False
    except Exception:
        return False


def migrate_manifest(cwd: str, board_slug: str) -> bool:
    """Copy legacy manifest to board-level location if it exists and board copy doesn't.

    Idempotent: no-ops if board manifest already exists. Does not delete legacy file.
    Returns True if migration happened or board manifest already exists.
    """
    try:
        board_mp = _board_manifest_path(board_slug)
        if board_mp.exists():
            return True  # Already migrated
        legacy_mp = _manifest_path(cwd)
        if not legacy_mp.exists():
            return True  # Nothing to migrate
        # Copy legacy → board location
        legacy_data = read_manifest(cwd)
        return write_manifest(cwd, legacy_data, board_slug=board_slug)
    except Exception:
        return False


def get_entry(manifest: dict, rel_path: str) -> dict | None:
    """Get a manifest entry by relative file path."""
    return manifest.get("artifacts", {}).get(rel_path)


def set_entry(
    manifest: dict,
    rel_path: str,
    context_id: str,
    context_label: str,
    file_hash_val: str,
    context_type: str,
    session_id: str,
) -> None:
    """Set or update a manifest entry."""
    if "artifacts" not in manifest:
        manifest["artifacts"] = {}
    manifest["artifacts"][rel_path] = {
        "context_id": context_id,
        "context_label": context_label,
        "captured_hash": file_hash_val,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "context_type": context_type,
        "session_id": session_id,
    }


def remove_entry(manifest: dict, rel_path: str) -> dict | None:
    """Remove a manifest entry. Returns the removed entry or None."""
    return manifest.get("artifacts", {}).pop(rel_path, None)


def to_relative(file_path: str, cwd: str) -> str:
    """Convert absolute path to relative path from cwd."""
    try:
        return os.path.relpath(file_path, cwd)
    except ValueError:
        # Different drives on Windows, etc.
        return file_path
