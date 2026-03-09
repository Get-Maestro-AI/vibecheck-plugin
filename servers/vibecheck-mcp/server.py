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
from urllib.parse import quote as url_quote

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Add project scripts to path for config/auth (stdlib-only libs)
_SCRIPTS_DIR = str(Path(__file__).parent.parent.parent / "scripts")
sys.path.insert(0, _SCRIPTS_DIR)

try:
    from lib.config import get_api_url  # type: ignore[import]
    from lib.auth import resolve_auth_headers  # type: ignore[import]
    from lib.hook_log import log_hook_issue  # type: ignore[import]
except ImportError:
    def get_api_url() -> str:
        return os.environ.get("VIBECHECK_API_URL", "http://localhost:8420")
    def resolve_auth_headers() -> dict:
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
        session_id, cwd = _get_session_context()
        payload = {
            "session_id": session_id,
            "cwd": cwd,
            "issue_id": issue_id,
            "resolution_note": resolution_note,
        }
        data = json.dumps(payload, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/dismiss-issue",
            data=data,
            headers={"Content-Type": "application/json", **resolve_auth_headers()},
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
        session_id, cwd = _get_session_context()
        payload = {
            "session_id": session_id,
            "cwd": cwd,
            "objective_id": objective_id,
            "trigger": trigger,
        }
        data = json.dumps(payload, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/begin-completion",
            data=data,
            headers={"Content-Type": "application/json", **resolve_auth_headers()},
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
        session_id, cwd = _get_session_context()
        payload = {
            "session_id": session_id,
            "cwd": cwd,
            "objective_id": objective_id,
            "checkpoint_summary": checkpoint_summary,
        }
        data = json.dumps(payload, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/finalize-objective",
            data=data,
            headers={"Content-Type": "application/json", **resolve_auth_headers()},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {"ok": True}
    except (URLError, OSError, Exception) as e:
        log_hook_issue("vibecheck-mcp", "Failed to POST /api/push/finalize-objective", e)
        return {"ok": False, "blocked": True, "reason": "finalize-objective request failed"}


def _api_call(method: str, path: str, payload: dict | None = None, timeout: int = 8) -> dict:
    """Make an HTTP call to the VibeCheck API and return JSON response."""
    try:
        api_url = get_api_url()
        url = f"{api_url}{path}"
        data = json.dumps(payload, default=str).encode() if payload else None
        req = urllib_request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", **resolve_auth_headers()},
            method=method,
        )
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {"ok": True}
    except (URLError, OSError, Exception) as e:
        log_hook_issue("vibecheck-mcp", f"API call failed: {method} {path}", e)
        return {"error": str(e)}


def post_mcp_report(report_data: dict) -> None:
    """POST an MCPReport to the VibeCheck server (fire and forget)."""
    try:
        api_url = get_api_url()
        data = json.dumps(report_data, default=str).encode()
        req = urllib_request.Request(
            f"{api_url}/api/push/mcp-report",
            data=data,
            headers={"Content-Type": "application/json", **resolve_auth_headers()},
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
        # ── Context Library tools ────────────────────────────────────────────
        types.Tool(
            name="vibecheck_list_contexts",
            description=(
                "List contexts from the VibeCheck Context Library. "
                "Returns id, title, type, status, and brief preview for each context. "
                "Use this to find specs to implement, issues to fix, or decisions to reference."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["research", "spec", "issue", "decision", "note", "standard"],
                        "description": "Filter by context type",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (draft, shaped, ready, dispatched, implemented, active, archived)",
                    },
                    "tag": {
                        "type": "string",
                        "description": "Filter by tag",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10)",
                    },
                },
            },
        ),
        types.Tool(
            name="vibecheck_get_context",
            description=(
                "Get full detail for a context including its brief, status history, "
                "linked sessions, and successor contexts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Context ID",
                    },
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="vibecheck_create_context",
            description=(
                "Create a new context in the VibeCheck Context Library. "
                "Use this to capture decisions, file issues, or create notes during a session. "
                "Defaults to type='note' for quick capture. Set type='decision' for architectural "
                "decisions, type='issue' for discovered gaps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Context title",
                    },
                    "brief": {
                        "type": "string",
                        "description": "Markdown content for the brief",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["research", "spec", "issue", "decision", "note", "standard"],
                        "description": "Context type (default: note)",
                    },
                    "predecessor_id": {
                        "type": "string",
                        "description": "ID of the context this follows from",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization",
                    },
                },
                "required": ["title"],
            },
        ),
        types.Tool(
            name="vibecheck_update_context",
            description=(
                "Update an existing context. Can change title, replace or append to brief, "
                "update tags, toggle always_inject, change status, or add notes to the status history."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Context ID to update",
                    },
                    "title": {
                        "type": "string",
                        "description": "Replace the context title",
                    },
                    "brief_replace": {
                        "type": "string",
                        "description": "Replace the entire brief content (mutually exclusive with brief_append)",
                    },
                    "brief_append": {
                        "type": "string",
                        "description": "Content to append to the brief (not replace)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Replace the full tag list",
                    },
                    "always_inject": {
                        "type": "boolean",
                        "description": "Update the always-inject flag (standard-layer contexts only)",
                    },
                    "source_snapshot": {
                        "type": "object",
                        "description": "Replace source metadata (e.g. issue severity, location)",
                    },
                    "status": {
                        "type": "string",
                        "description": "New status",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notes added to status history if status changes",
                    },
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="vibecheck_link_context",
            description=(
                "Link a Claude Code session to a context. Use this to connect "
                "the current session to a spec or issue being worked on."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "context_id": {
                        "type": "string",
                        "description": "Context ID to link",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Session ID (defaults to current session)",
                    },
                    "link_type": {
                        "type": "string",
                        "enum": ["dispatched", "worked_on", "referenced"],
                        "description": "Type of link (default: worked_on)",
                    },
                },
                "required": ["context_id"],
            },
        ),
        types.Tool(
            name="vibecheck_find_related",
            description=(
                "Find semantically related contexts by free-text query. "
                "Use this to find relevant past decisions before making a new one. "
                "Example: 'Is there a prior decision about how we handle auth tokens?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Free text describing the problem or decision needed",
                    },
                    "layer": {
                        "type": "string",
                        "enum": ["decision", "standard"],
                        "description": "Layer to search (default: decision)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 5)",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="vibecheck_get_active_context_set",
            description=(
                "Load the full active context set for a context: the context's brief, "
                "semantically retrieved decision contexts, and all always-inject standard "
                "contexts. Use this at session start to load full context for a task."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "context_id": {
                        "type": "string",
                        "description": "Context ID to load the active set for",
                    },
                },
                "required": ["context_id"],
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

    # ── Context Library tool handlers ────────────────────────────────────────

    if name == "vibecheck_list_contexts":
        params = []
        if arguments.get("type"):
            params.append(f"type={arguments['type']}")
        if arguments.get("status"):
            params.append(f"status={arguments['status']}")
        if arguments.get("tag"):
            params.append(f"tag={arguments['tag']}")
        limit = arguments.get("limit", 10)
        params.append(f"limit={limit}")
        qs = "&".join(params)
        result = _api_call("GET", f"/api/contexts?{qs}")
        contexts = result.get("contexts", [])
        if not contexts:
            return [types.TextContent(type="text", text="No contexts found matching filters.")]
        lines = []
        for c in contexts:
            status = c.get("status", "")
            preview = c.get("brief_preview", "")[:100]
            lines.append(f"- [{c['type']}] **{c['title']}** ({status}) id={c['id']}\n  {preview}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "vibecheck_get_context":
        ctx_id = url_quote(arguments.get("id", ""), safe="")
        result = _api_call("GET", f"/api/contexts/{ctx_id}")
        if result.get("error") or not result.get("id"):
            return [types.TextContent(type="text", text=f"Context not found: {ctx_id}")]
        label = result.get('label')
        lines = [
            f"# {result['title']}",
            f"**Type:** {result['type']} | **Status:** {result['status']} | **Layer:** {result['layer']}",
        ]
        if label:
            lines[0] = f"# {label} — {result['title']}"
        if result.get("predecessor_id"):
            lines.append(f"**Predecessor:** {result['predecessor_id']}")
        if result.get("successor_ids"):
            lines.append(f"**Successors:** {', '.join(result['successor_ids'])}")
        if result.get("tags"):
            lines.append(f"**Tags:** {', '.join(result['tags'])}")
        lines.append(f"\n## Brief\n{result.get('brief', '(empty)')}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "vibecheck_create_context":
        session_id, cwd = _get_session_context()
        payload = {
            "title": arguments.get("title", ""),
            "type": arguments.get("type", "note"),
            "brief": arguments.get("brief", ""),
            "created_by": "agent",
            "source_type": "agent",
        }
        if arguments.get("predecessor_id"):
            payload["predecessor_id"] = arguments["predecessor_id"]
        if arguments.get("tags"):
            payload["tags"] = arguments["tags"]
        result = _api_call("POST", "/api/contexts", payload)
        if result.get("error"):
            return [types.TextContent(type="text", text=f"Failed to create context: {result['error']}")]

        # Link the new context to the current session
        ctx_id = result.get("id")
        if ctx_id and session_id and session_id != "unknown":
            _api_call("POST", f"/api/contexts/{ctx_id}/link-session", {
                "session_id": session_id,
                "link_type": "created_in",
            })

        return [types.TextContent(
            type="text",
            text=f"Context created: [{result.get('type', 'note')}] \"{result.get('title', '')}\" (id={result.get('id', '')})",
        )]

    if name == "vibecheck_update_context":
        ctx_id = url_quote(arguments.get("id", ""), safe="")

        # Mutual exclusion check
        if arguments.get("brief_append") and arguments.get("brief_replace") is not None:
            return [types.TextContent(
                type="text",
                text="Error: brief_append and brief_replace are mutually exclusive.",
            )]

        # Build PATCH payload for field updates
        patch: dict = {}
        if arguments.get("title"):
            patch["title"] = arguments["title"]
        if "tags" in arguments:
            patch["tags"] = arguments["tags"]
        if "always_inject" in arguments:
            patch["always_inject"] = arguments["always_inject"]
        if "source_snapshot" in arguments:
            patch["source_snapshot"] = arguments["source_snapshot"]

        # Brief handling: replace or append
        if arguments.get("brief_replace") is not None:
            patch["brief"] = arguments["brief_replace"]
        elif arguments.get("brief_append"):
            existing = _api_call("GET", f"/api/contexts/{ctx_id}")
            if existing.get("id"):
                new_brief = (existing.get("brief", "") or "").rstrip()
                if new_brief:
                    new_brief += "\n\n---\n\n"
                new_brief += arguments["brief_append"]
                patch["brief"] = new_brief

        # Apply field updates
        if patch:
            _api_call("PATCH", f"/api/contexts/{ctx_id}", patch)

        # Handle status change (separate endpoint with state machine)
        if arguments.get("status"):
            evidence = {}
            if arguments.get("notes"):
                evidence["notes"] = arguments["notes"]
            _api_call("POST", f"/api/contexts/{ctx_id}/status", {
                "status": arguments["status"],
                "source": "explicit",
                "evidence": evidence if evidence else None,
            })

        # Fetch updated
        result = _api_call("GET", f"/api/contexts/{ctx_id}")
        if result.get("error") or not result.get("id"):
            return [types.TextContent(type="text", text=f"Context not found: {ctx_id}")]
        return [types.TextContent(
            type="text",
            text=f"Context updated: \"{result['title']}\" — status={result['status']}",
        )]

    if name == "vibecheck_link_context":
        ctx_id = url_quote(arguments.get("context_id", ""), safe="")
        sid = arguments.get("session_id") or session_id
        link_type = arguments.get("link_type", "worked_on")
        result = _api_call("POST", f"/api/contexts/{ctx_id}/link-session", {
            "session_id": sid,
            "link_type": link_type,
        })
        if result.get("error"):
            return [types.TextContent(type="text", text=f"Link failed: {result['error']}")]
        return [types.TextContent(type="text", text=f"Session {sid} linked to context {ctx_id} ({link_type}).")]

    if name == "vibecheck_find_related":
        query = arguments.get("query", "")
        layer = arguments.get("layer", "decision")
        limit = arguments.get("limit", 5)
        result = _api_call("GET", f"/api/contexts/related?q={url_quote(query)}&layer={layer}&limit={limit}")
        related = result.get("related", [])
        if not related:
            return [types.TextContent(type="text", text="No related contexts found.")]
        lines = []
        for r in related:
            sim = r.get("similarity", 0)
            brief = (r.get("brief", "") or "")[:200]
            lines.append(f"- [{r['type']}] **{r['title']}** (similarity={sim:.2f}) id={r['id']}\n  {brief}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "vibecheck_get_active_context_set":
        ctx_id = url_quote(arguments.get("context_id", ""), safe="")
        result = _api_call("GET", f"/api/contexts/active-set?context_id={ctx_id}")
        if result.get("error"):
            return [types.TextContent(type="text", text=f"Failed to load active context set: {result['error']}")]
        lines = ["# Active Context Set\n"]
        work = result.get("work", {})
        if work:
            lines.append(f"## Task ({work.get('type', 'spec')}): {work.get('title', '')}")
            lines.append(work.get("brief", "(empty)"))
            lines.append("")
        decisions = result.get("decisions", [])
        if decisions:
            lines.append("## Relevant Past Decisions")
            for d in decisions:
                brief = (d.get("brief", "") or "")[:500]
                lines.append(f"### {d['title']}\n{brief}\n")
        standards = result.get("standards", [])
        if standards:
            lines.append("## Standing Standards")
            for s in standards:
                lines.append(f"### {s['title']}\n{s.get('brief', '')}\n")
        return [types.TextContent(type="text", text="\n".join(lines))]

    # ── Existing tools ────────────────────────────────────────────────────────

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
