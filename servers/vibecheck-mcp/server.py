#!/usr/bin/env python3
"""VibeCheck MCP server — semantic self-reporting tools for Claude.

Provides one unified telemetry tool for regular status updates:
  vibecheck_update           — checkpoint updates with optional progress detail

And dedicated completion/maintenance tools.

Each tool call generates an MCPReport that gets POSTed to the VibeCheck
server at /api/push/mcp-report, enabling:
  - Dashboard live status updates
  - AlignmentCheckDetector fast path (no LLM call when MCP data present)
  - PromptDriftDetector (checkpoint vs. first prompt)

The server is launched by Claude Code when .mcp.json is present in the
project root, and runs as a stdio subprocess.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Add project scripts to path for config/auth (stdlib-only libs)
_SCRIPTS_DIR = str(Path(__file__).parent.parent.parent / "scripts")
sys.path.insert(0, _SCRIPTS_DIR)

try:
    from lib.config import get_api_url  # type: ignore[import]
    from lib.auth import resolve_credentials  # type: ignore[import]
    from lib.hook_log import log_hook_issue  # type: ignore[import]
except ImportError:
    def get_api_url() -> str:
        return os.environ.get("VIBECHECK_API_URL", "http://localhost:8420")
    def resolve_credentials() -> dict:
        return {}
    def log_hook_issue(script: str, message: str, exc: Exception | None = None) -> None:
        try:
            note = f"[{script}] {message}"
            if exc:
                note += f" | {type(exc).__name__}: {exc}"
            print(note, file=sys.stderr)
        except Exception:
            return


def post_dismiss_issue(issue_id: str, resolution_note: str = "") -> dict:
    """POST a dismiss-issue request and return server result."""
    try:
        api_url = get_api_url()
        creds = resolve_credentials()
        session_id, cwd = _get_session_context()
        payload = {
            "session_id": session_id,
            "cwd": cwd,
            "issue_id": issue_id,
            "resolution_note": resolution_note,
            **creds,
        }
        data = json.dumps(payload, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/dismiss-issue",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if body:
                try:
                    return json.loads(body)
                except Exception:
                    return {"ok": True}
            return {"ok": True}
    except (URLError, OSError, Exception) as e:
        log_hook_issue("vibecheck-mcp", "Failed to POST /api/push/dismiss-issue", e)
        return {"ok": False, "dismissed": 0}


def post_begin_completion(objective_id: str = "", trigger: str = "manual") -> dict:
    """POST begin-completion handshake request and return server payload."""
    try:
        api_url = get_api_url()
        creds = resolve_credentials()
        session_id, cwd = _get_session_context()
        payload = {
            "session_id": session_id,
            "cwd": cwd,
            "objective_id": objective_id,
            "trigger": trigger,
            **creds,
        }
        data = json.dumps(payload, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/begin-completion",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {"ok": True}
    except (URLError, OSError, Exception) as e:
        log_hook_issue("vibecheck-mcp", "Failed to POST /api/push/begin-completion", e)
        return {"ok": False, "blocked": True, "reason": "begin-completion request failed"}


def post_finalize_objective(objective_id: str = "", checkpoint_summary: str = "") -> dict:
    """POST finalize-objective request and return server payload."""
    try:
        api_url = get_api_url()
        creds = resolve_credentials()
        session_id, cwd = _get_session_context()
        payload = {
            "session_id": session_id,
            "cwd": cwd,
            "objective_id": objective_id,
            "checkpoint_summary": checkpoint_summary,
            **creds,
        }
        data = json.dumps(payload, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/finalize-objective",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {"ok": True}
    except (URLError, OSError, Exception) as e:
        log_hook_issue("vibecheck-mcp", "Failed to POST /api/push/finalize-objective", e)
        return {"ok": False, "blocked": True, "reason": "finalize-objective request failed"}


def post_mcp_report(report_data: dict) -> None:
    """POST an MCPReport to the VibeCheck server (fire and forget)."""
    try:
        api_url = get_api_url()
        creds = resolve_credentials()
        payload = {**report_data, **creds}
        data = json.dumps(payload, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/mcp-report",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=5):
            pass
    except (URLError, OSError, Exception) as e:
        log_hook_issue("vibecheck-mcp", "Failed to POST /api/push/mcp-report", e)


def _get_session_context() -> tuple[str, str]:
    """Return (session_id, cwd) from Claude Code's hook environment."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    cwd = os.environ.get("CLAUDE_CWD", os.getcwd())
    return session_id, cwd


# ── MCP Server definition ─────────────────────────────────────────────────────

app = Server("vibecheck")
_EVENT_SEQ = 0


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="vibecheck_update",
            description=(
                "Report your current work phase to the VibeCheck monitoring dashboard. "
                "Call this at every meaningful checkpoint: when you begin a new task, "
                "when you complete a subtask or file edit, when you switch phases "
                "(planning → implementing → debugging → reviewing), and when you are "
                "about to stop responding. Set status_label to match your actual phase "
                "and include a 1-2 sentence summary of what changed. This is your "
                "primary reporting tool — use it continuously, not just at the end."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "current_task": {
                        "type": "string",
                        "description": "What you are currently working on (1 sentence)",
                    },
                    "completed_subtasks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of subtasks completed in this turn",
                    },
                    "files_modified": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files modified in this turn",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Your confidence level in the current approach",
                    },
                    "status_label": {
                        "type": "string",
                        "enum": ["planning", "implementing", "debugging", "reviewing", "done"],
                        "description": "Current work phase",
                    },
                    "summary": {
                        "type": "string",
                        "description": "1-2 sentence checkpoint summary",
                    },
                    "next_step": {
                        "type": "string",
                        "description": "What you plan to do next",
                    },
                },
                "required": ["status_label", "summary"],
            },
        ),
        types.Tool(
            name="vibecheck_dismiss_issue",
            description=(
                "Dismiss a specific blocking issue from the VibeCheck dashboard after "
                "you have fixed it. Call this after successfully resolving an issue "
                "identified by /vibecheck:review. Keeps the dashboard accurate "
                "so the developer sees real-time fix progress without re-running the full review."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id": {
                        "type": "string",
                        "description": "The full project-prefixed issue ID to dismiss, e.g. 'VC-401', 'VC-402'. Always use the label shown on the issue card, not a bare number.",
                    },
                    "resolution_note": {
                        "type": "string",
                        "description": "Brief description of how the issue was fixed",
                    },
                },
                "required": ["issue_id"],
            },
        ),
        types.Tool(
            name="vibecheck_begin_completion",
            description=(
                "Begin objective completion protocol. Call this when work is ready "
                "for final review. Returns the scoped files list and marks the "
                "objective as pending protocol completion. Prefer /vibecheck:complete "
                "as the default completion workflow."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "objective_id": {
                        "type": "string",
                        "description": "Optional explicit objective id override",
                    },
                    "trigger": {
                        "type": "string",
                        "enum": ["manual", "checkpoint_done", "session_end"],
                        "description": "Why completion protocol is starting",
                    },
                },
            },
        ),
        types.Tool(
            name="vibecheck_finalize_objective",
            description=(
                "Finalize objective after completion protocol is complete. "
                "This is blocked until a review payload has been submitted. "
                "Prefer /vibecheck:complete for normal completion."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "objective_id": {
                        "type": "string",
                        "description": "Optional explicit objective id override",
                    },
                    "checkpoint_summary": {
                        "type": "string",
                        "description": "Optional short completion summary",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    global _EVENT_SEQ
    session_id, cwd = _get_session_context()

    # vibecheck_dismiss_issue uses a dedicated endpoint, not the MCPReport path
    if name == "vibecheck_dismiss_issue":
        issue_id = arguments.get("issue_id", "")
        resolution_note = arguments.get("resolution_note", "")
        result = post_dismiss_issue(issue_id, resolution_note)
        dismissed = int(result.get("dismissed", 0) or 0) if isinstance(result, dict) else 0
        note = f" ({resolution_note})" if resolution_note else ""
        if dismissed > 0:
            text = f"Issue {issue_id} dismissed from VibeCheck{note}."
        else:
            text = (
                f"Issue {issue_id} was not dismissed (no matching active issue found){note}."
            )
        return [types.TextContent(type="text", text=text)]

    if name == "vibecheck_begin_completion":
        result = post_begin_completion(
            objective_id=arguments.get("objective_id", ""),
            trigger=arguments.get("trigger", "manual"),
        )
        if result.get("ok"):
            files = result.get("files_to_review") or []
            return [types.TextContent(
                type="text",
                text=(
                    f"Completion protocol started for {result.get('objective_id', '')}. "
                    f"{len(files)} file(s) scoped for review."
                ),
            )]
        return [types.TextContent(type="text", text=f"Begin completion blocked: {result.get('reason', 'unknown error')}")]

    if name == "vibecheck_finalize_objective":
        result = post_finalize_objective(
            objective_id=arguments.get("objective_id", ""),
            checkpoint_summary=arguments.get("checkpoint_summary", ""),
        )
        if result.get("ok"):
            return [types.TextContent(type="text", text=f"Objective finalized: {result.get('objective_id', '')}")]
        return [types.TextContent(
            type="text",
            text=(
                f"Finalize blocked: {result.get('reason', 'unknown error')} "
                f"(protocol_status={result.get('protocol_status', 'unknown')})"
            ),
        )]

    if name == "vibecheck_update":
        status_label = (arguments.get("status_label") or "").strip()
        summary = (arguments.get("summary") or "").strip()
        if status_label not in {"planning", "implementing", "debugging", "reviewing", "done"}:
            return [types.TextContent(
                type="text",
                text=(
                    "Update blocked: status_label must be one of "
                    "'planning', 'implementing', 'debugging', 'reviewing', or 'done'."
                ),
            )]
        if not summary:
            return [types.TextContent(
                type="text",
                text="Update blocked: include summary.",
            )]
    report_type = _tool_to_report_type(name)
    if name == "vibecheck_update":
        report_type = "checkpoint"

    report: dict = {
        "session_id": session_id,
        "cwd": cwd,
        "event_uuid": str(uuid.uuid4()),
        "event_seq": _EVENT_SEQ + 1,
        "report_type": report_type,
        **arguments,
    }
    _EVENT_SEQ += 1

    post_mcp_report(report)

    # Enforce completion handshake on done checkpoint updates: attempt finalize
    # and return a blocked message when protocol review has not completed yet.
    if name == "vibecheck_update" and arguments.get("status_label") == "done":
        result = post_finalize_objective(
            objective_id=arguments.get("objective_id", ""),
            checkpoint_summary=arguments.get("summary", ""),
        )
        if result.get("ok"):
            return [types.TextContent(
                type="text",
                text=(
                    f"Done checkpoint accepted; objective finalized "
                    f"({result.get('objective_id', '')})."
                ),
            )]
        return [types.TextContent(
            type="text",
            text=(
                "Done checkpoint blocked until completion protocol finishes. "
                f"{result.get('next_action', result.get('reason', 'Run review then finalize.'))}"
            ),
        )]

    # Return a brief acknowledgment (not shown to user unless debug mode)
    ack_messages = {
        "vibecheck_update": (
            f"Checkpoint reported ({arguments.get('status_label', '')}): "
            f"{arguments.get('summary', '')}"
        ),
        "vibecheck_dismiss_issue": f"Issue {arguments.get('issue_id', '')} dismissed.",
        "vibecheck_begin_completion": "Completion protocol started.",
        "vibecheck_finalize_objective": "Objective finalize requested.",
    }
    msg = ack_messages.get(name, "Reported to VibeCheck.")
    return [types.TextContent(type="text", text=msg)]


def _tool_to_report_type(tool_name: str) -> str:
    return {
        "vibecheck_update": "checkpoint",
    }.get(tool_name, "progress")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_opts = app.create_initialization_options()
        await app.run(read_stream, write_stream, init_opts)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
