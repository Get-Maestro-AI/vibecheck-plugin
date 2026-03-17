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
import os
import sys
import hashlib
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError

# Add lib/ to path (works regardless of cwd)
sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import get_auth_headers_for_index  # type: ignore[import]
from lib.config import get_api_targets  # type: ignore[import]
from lib.fanout import post_to_targets  # type: ignore[import]
from lib.hook_log import log_hook_issue  # type: ignore[import]
from lib.transcript import detect_waiting_context  # type: ignore[import]


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

    # On PreToolUse, scan the JSONL tail to detect user-blocking tool calls.
    # This lets the backend set waiting status without hardcoding tool names.
    waiting_context = None
    if hook_data.get("hook_event_name") == "PreToolUse":
        transcript_path = hook_data.get("transcript_path", "")
        if transcript_path:
            try:
                waiting_context = detect_waiting_context(transcript_path)
            except Exception:
                pass

    payload = {
        **hook_data,
        "event_id": _build_event_id(hook_data),
        "event_source": "push_event",
        "plugin_version": "1.0.0",
    }
    if waiting_context is not None:
        payload["waiting_context"] = waiting_context

    # Register PPID → session_id on SessionStart (including resume/compact).
    # Delete on SessionEnd. This lets the MCP server resolve its own session_id
    # via os.getppid() without relying on CLAUDE_SESSION_ID (not set in MCP envs).
    # Both operations fan-out to all configured targets so each instance has the mapping.
    event_name = hook_data.get("hook_event_name", "")
    session_id = hook_data.get("session_id", "")
    if event_name == "SessionStart" and session_id and session_id != "unknown":
        try:
            ppid = os.getppid()
            cwd = hook_data.get("cwd", "")
            project_name = hook_data.get("project_name") or (cwd.split("/")[-1] if cwd else "")
            post_to_targets(
                "/api/push/session-ppid",
                {"ppid": ppid, "session_id": session_id, "project_name": project_name},
                timeout=3,
            )
        except Exception as e:
            log_hook_issue("push_event", f"Failed to register PPID session (ppid={os.getppid()})", e)
    elif event_name == "SessionEnd" and session_id:
        try:
            ppid = os.getppid()
            targets = get_api_targets()
            for n, target_url in enumerate(targets, start=1):
                try:
                    t_headers = get_auth_headers_for_index(n)
                    del_req = urllib_request.Request(
                        f"{target_url}/api/push/session-ppid/{ppid}",
                        headers={"Content-Type": "application/json", **t_headers},
                        method="DELETE",
                    )
                    with urllib_request.urlopen(del_req, timeout=3):
                        pass
                except Exception as e:
                    if n == 1:
                        log_hook_issue("push_event", f"Failed to delete PPID session (ppid={ppid})", e)
        except Exception as e:
            log_hook_issue("push_event", f"Failed to delete PPID session (ppid={os.getppid()})", e)

    post_to_targets("/api/push/hook-event", payload)


if __name__ == "__main__":
    main()
