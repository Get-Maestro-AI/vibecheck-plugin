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
import hashlib
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import resolve_credentials  # type: ignore[import]
from lib.config import get_api_url  # type: ignore[import]
from lib.hook_log import log_hook_issue  # type: ignore[import]


def _build_event_id(hook_data: dict) -> str:
    stable = {
        k: v for k, v in hook_data.items()
        if k not in {"event_id", "event_seq", "event_source", "plugin_version"}
    }
    blob = json.dumps(stable, sort_keys=True, default=str)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()[:16]


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
    except Exception as e:
        log_hook_issue("session_baseline", "Failed to parse hook payload JSON", e)
        sys.exit(0)

    cwd = hook_data.get("cwd", "")

    if not cwd or not os.path.isdir(cwd):
        log_hook_issue("session_baseline", "Missing cwd or cwd is not a directory")
        sys.exit(0)

    # Collect git context
    git_branch = run(["git", "branch", "--show-current"], cwd)
    git_status = run(["git", "status", "--short"], cwd)
    git_log = run(["git", "log", "--oneline", "-10"], cwd)
    git_remote = run(["git", "remote", "get-url", "origin"], cwd)

    # Uncommitted file count
    total_uncommitted = len([line for line in git_status.splitlines() if line.strip()])

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
    except Exception as e:
        log_hook_issue("session_baseline", "Failed to resolve credentials", e)

    payload = {
        **hook_data,
        **creds,
        "event_id": _build_event_id(hook_data),
        "event_source": "session_baseline",
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
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:800]
        except Exception:
            body = ""
        log_hook_issue(
            "session_baseline",
            (
                "Failed to POST /api/push/hook-event "
                f"(status={e.code}, response={body})"
            ),
            e,
        )
    except (URLError, OSError, Exception) as e:
        log_hook_issue("session_baseline", "Failed to POST /api/push/hook-event", e)


if __name__ == "__main__":
    main()
