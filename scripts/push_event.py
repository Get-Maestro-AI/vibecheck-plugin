#!/usr/bin/env python3
"""Generic hook event pusher.

Reads Claude Code hook JSON from stdin, adds auth credentials,
and POSTs to ${VIBECHECK_API_URL}/api/push/hook-event.

Used by: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
         PostToolUseFailure, SubagentStart, SubagentStop,
         Stop (after push_turn.py), SessionEnd.

Uses only stdlib (urllib, json, sys) — no venv required.
Always exits 0; never blocks Claude Code.
"""
import json
import sys
import os
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

# Add lib/ to path (works regardless of cwd)
sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import resolve_credentials  # type: ignore[import]
from lib.config import get_api_url  # type: ignore[import]


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)  # Never block Claude Code on bad input

    creds = {}
    try:
        creds = resolve_credentials()
    except Exception:
        pass

    payload = {**hook_data, **creds, "plugin_version": "1.0.0"}

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
    except (URLError, OSError, Exception):
        pass  # Silent failure — never block Claude Code


if __name__ == "__main__":
    main()
