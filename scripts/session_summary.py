#!/usr/bin/env python3
"""Session summary extraction (SessionEnd, synchronous, 15s timeout).

Reads the full JSONL transcript once at session end, produces a
SessionSummaryPayload, and POSTs it as an extended HookEvent to the server.

Sync is justified here: SessionEnd fires after the session is over, so
blocking has no UX cost. An async: true on SessionEnd would create a race
condition where Claude Code kills the subprocess before the transcript read
completes.

Always exits 0. Uses only stdlib (plus lib/transcript.py from this repo).
"""
import json
import os
import sys
import signal
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import resolve_credentials  # type: ignore[import]
from lib.config import get_api_url  # type: ignore[import]
from lib.transcript import parse_transcript  # type: ignore[import]

# Internal parse timeout: if transcript parse exceeds this, send what we have
PARSE_TIMEOUT_S = 10


def with_timeout(fn, timeout_s: int, fallback):
    """Run fn() with a timeout; return fallback if exceeded (Unix only)."""
    try:
        def _timeout_handler(signum, frame):
            raise TimeoutError("parse timeout")

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout_s)
        try:
            result = fn()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        return result
    except (TimeoutError, AttributeError):
        # AttributeError: SIGALRM not available on Windows
        return fallback


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    transcript_path = hook_data.get("transcript_path", "")
    if not transcript_path or not os.path.exists(transcript_path):
        sys.exit(0)

    # Parse with internal timeout
    fallback_payload = {
        "first_prompt": "", "final_prompt": "", "total_turns": 0,
        "tool_call_counts": {}, "token_usage": {}, "model": "",
        "objectives_raw": [], "conversation_window": [],
        "files_modified": [], "error_count": 0, "consecutive_errors": 0,
    }

    session_summary = with_timeout(
        lambda: parse_transcript(transcript_path),
        PARSE_TIMEOUT_S,
        fallback_payload,
    )

    creds = {}
    try:
        creds = resolve_credentials()
    except Exception:
        pass

    payload = {
        **hook_data,
        **creds,
        "session_summary": session_summary,
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
