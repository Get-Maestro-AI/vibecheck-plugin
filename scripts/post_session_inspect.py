#!/usr/bin/env python3
"""Post-session code inspection (SessionEnd, async, 25s timeout).

Runs grep -rn TODO/FIXME and an optional build/test command once at session end.
POSTs InspectionResults as an extended HookEvent to the server.
Results arrive piecemeal (TODOs first, then build) so partial data is useful.

Async is correct here: build commands can legitimately exceed any timeout.
Each result is POSTed incrementally so partial data arrives even if killed.

Always exits 0. Uses only stdlib. Targets at most a few seconds for grep;
build command is bounded by hook timeout set in hooks.json (25s).
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

MAX_TODOS = 30
MAX_FIXMES = 30
GREP_TIMEOUT = 8
BUILD_TIMEOUT = 20


def push_inspection(hook_data: dict, creds: dict, inspection: dict) -> None:
    """POST inspection results to the server (fire and forget)."""
    payload = {
        **hook_data,
        **creds,
        "inspection_results": inspection,
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
        with urllib_request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def grep_pattern(pattern: str, cwd: str, max_results: int) -> list[dict]:
    """Run grep -rn PATTERN in cwd, return up to max_results hits."""
    results = []
    try:
        proc = subprocess.run(
            ["grep", "-rn", "--include=*.py", "--include=*.ts", "--include=*.tsx",
             "--include=*.js", "--include=*.jsx", "--include=*.go",
             "--exclude-dir=.git", "--exclude-dir=node_modules",
             "--exclude-dir=.venv", "--exclude-dir=__pycache__",
             pattern, "."],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GREP_TIMEOUT,
        )
        for line in proc.stdout.splitlines()[:max_results]:
            parts = line.split(":", 2)
            if len(parts) >= 3:
                results.append({
                    "file": parts[0],
                    "line": parts[1],
                    "text": parts[2].strip()[:200],
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    return results


def detect_build_command(cwd: str) -> list[str] | None:
    """Heuristically detect the build/test command for the project."""
    cwd_path = Path(cwd)
    if (cwd_path / "package.json").exists():
        try:
            pkg = json.loads((cwd_path / "package.json").read_text())
            scripts = pkg.get("scripts", {})
            if "build" in scripts:
                return ["npm", "run", "build", "--silent"]
        except Exception:
            pass
    if (cwd_path / "pyproject.toml").exists():
        return ["python", "-m", "pytest", "--tb=no", "-q", "--no-header"]
    if (cwd_path / "Makefile").exists():
        # Don't auto-run make — it might do destructive things
        pass
    return None


def count_uncommitted(cwd: str) -> int:
    """Count uncommitted files."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=cwd, capture_output=True, text=True, timeout=5
        )
        return len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        return 0


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cwd = hook_data.get("cwd", "")
    if not cwd or not os.path.isdir(cwd):
        sys.exit(0)

    creds = {}
    try:
        creds = resolve_credentials()
    except Exception:
        pass

    # Phase 1: TODOs and FIXMEs (fast grep — POST immediately)
    todos = grep_pattern("TODO", cwd, MAX_TODOS)
    fixmes = grep_pattern("FIXME", cwd, MAX_FIXMES)
    uncommitted = count_uncommitted(cwd)

    inspection: dict = {
        "todos_found": todos,
        "fixmes_found": fixmes,
        "build_status": None,
        "build_output": None,
        "test_status": None,
        "uncommitted_file_count": uncommitted,
        "files_never_touched": [],
    }

    # Push partial results (grep findings) immediately
    push_inspection(hook_data, creds, inspection)

    # Phase 2: optional build check (only if a build command is detected)
    build_cmd = detect_build_command(cwd)
    if build_cmd:
        try:
            result = subprocess.run(
                build_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT,
            )
            status = "pass" if result.returncode == 0 else "fail"
            output = (result.stdout + result.stderr)[:2000]
            inspection["build_status"] = status
            inspection["build_output"] = output
            # Push updated results with build outcome
            push_inspection(hook_data, creds, inspection)
        except subprocess.TimeoutExpired:
            inspection["build_status"] = "error"
            inspection["build_output"] = "Build command timed out"
            push_inspection(hook_data, creds, inspection)
        except Exception:
            pass


if __name__ == "__main__":
    main()
