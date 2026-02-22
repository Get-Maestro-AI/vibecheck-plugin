#!/usr/bin/env python3
"""Session baseline capture.

Runs on SessionStart (async, 15s timeout).
Reads cwd from hook stdin, collects git context and project structure,
and POSTs an extended HookEvent with session_baseline payload to the server.

Uses only stdlib. Always exits 0.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import resolve_credentials  # type: ignore[import]
from lib.config import get_api_url  # type: ignore[import]


def run(cmd: list[str], cwd: str, timeout: int = 5) -> str:
    """Run a subprocess and return stdout, or '' on any failure."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cwd = hook_data.get("cwd", "")
    session_id = hook_data.get("session_id", "")

    if not cwd or not os.path.isdir(cwd):
        sys.exit(0)

    # Collect git context
    git_branch = run(["git", "branch", "--show-current"], cwd)
    git_status = run(["git", "status", "--short"], cwd)
    git_log = run(["git", "log", "--oneline", "-10"], cwd)
    git_remote = run(["git", "remote", "get-url", "origin"], cwd)

    # Uncommitted file count
    total_uncommitted = len([l for l in git_status.splitlines() if l.strip()])

    # Top-level directory listing (bounded)
    try:
        directory_listing = sorted(os.listdir(cwd))[:50]
    except Exception:
        directory_listing = []

    # package.json / pyproject.toml if present
    package_json: dict | None = None
    pyproject_toml: dict | None = None
    try:
        pkg_path = Path(cwd) / "package.json"
        if pkg_path.exists():
            import json as _json
            data = _json.loads(pkg_path.read_text()[:4096])
            package_json = {k: data.get(k) for k in ("name", "version", "scripts") if k in data}
    except Exception:
        pass
    try:
        ppt_path = Path(cwd) / "pyproject.toml"
        if ppt_path.exists():
            # Minimal parse: just grab [project] name/version without tomllib
            text = ppt_path.read_text()[:2048]
            pyproject_toml = {"raw_excerpt": text[:500]}
    except Exception:
        pass

    # Determine start reason from hook data
    session_start_reason = hook_data.get("session_start_reason", "")

    session_baseline = {
        "git_branch": git_branch,
        "git_status": git_status[:2000],
        "git_log": git_log[:2000],
        "git_remote": git_remote,
        "directory_listing": directory_listing,
        "package_json": package_json,
        "pyproject_toml": pyproject_toml,
        "total_uncommitted_files": total_uncommitted,
        "session_start_reason": session_start_reason,
    }

    creds = {}
    try:
        creds = resolve_credentials()
    except Exception:
        pass

    payload = {
        **hook_data,
        **creds,
        "session_baseline": session_baseline,
        "plugin_version": "1.0.0",
    }

    try:
        api_url = get_api_url()
        data = json.dumps(payload, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/hook-event",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=10):
            pass
    except (URLError, OSError, Exception):
        pass


if __name__ == "__main__":
    main()
