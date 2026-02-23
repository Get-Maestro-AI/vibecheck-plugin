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
import hashlib
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError

# Add lib/ to path (works regardless of cwd)
sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import resolve_credentials  # type: ignore[import]
from lib.config import get_api_url  # type: ignore[import]
from lib.hook_log import log_hook_issue  # type: ignore[import]


def _build_event_id(hook_data: dict) -> str:
    """Build a deterministic ID for this hook payload."""
    stable = {
        k: v for k, v in hook_data.items()
        if k not in {"event_id", "event_seq", "event_source", "plugin_version"}
    }
    blob = json.dumps(stable, sort_keys=True, default=str)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception) as e:
        log_hook_issue("push_event", "Failed to parse hook payload JSON", e)
        sys.exit(0)  # Never block Claude Code on bad input

    creds = {}
    try:
        creds = resolve_credentials()
    except Exception as e:
        log_hook_issue("push_event", "Failed to resolve credentials", e)

    payload = {
        **hook_data,
        **creds,
        "event_id": _build_event_id(hook_data),
        "event_source": "push_event",
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
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:800]
        except Exception:
            body = ""
        log_hook_issue(
            "push_event",
            (
                "Failed to POST /api/push/hook-event "
                f"(status={e.code}, event={hook_data.get('hook_event_name')}, "
                f"tool={hook_data.get('tool_name')}, keys={sorted(hook_data.keys())}, "
                f"response={body})"
            ),
            e,
        )
    except (URLError, OSError, Exception) as e:
        log_hook_issue(
            "push_event",
            (
                "Failed to POST /api/push/hook-event "
                f"(event={hook_data.get('hook_event_name')}, tool={hook_data.get('tool_name')})"
            ),
            e,
        )


if __name__ == "__main__":
    main()
