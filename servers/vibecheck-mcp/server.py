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
    from lib.config import get_api_url, get_frontend_url, get_api_targets  # type: ignore[import]
    from lib.auth import resolve_auth_headers, get_auth_headers_for_index  # type: ignore[import]
    from lib.hook_log import log_hook_issue  # type: ignore[import]
except ImportError:
    def _read_vibecheck_config(key: str) -> str:
        try:
            cfg = os.path.expanduser("~/.config/vibecheck/config")
            with open(cfg) as _f:
                for _ln in _f:
                    if _ln.startswith(f"{key}="):
                        return _ln.split("=", 1)[1].strip().rstrip("/")
        except Exception:
            pass
        return ""

    def get_api_url() -> str:
        url = os.environ.get("VIBECHECK_API_URL", "").strip().rstrip("/")
        return url or _read_vibecheck_config("api_url") or "http://localhost:8420"

    def get_api_targets() -> list:
        primary = get_api_url()
        targets = [primary]
        for n in range(2, 10):
            env_val = os.environ.get(f"VIBECHECK_API_URL_{n}", "").strip().rstrip("/")
            if env_val:
                url = env_val
            else:
                url = _read_vibecheck_config(f"api_url_{n}")
                if not url:
                    break
            if url and url not in targets:
                targets.append(url)
        return targets

    def get_frontend_url() -> str:
        url = os.environ.get("VIBECHECK_FRONTEND_URL", "").strip().rstrip("/")
        return url or _read_vibecheck_config("frontend_url") or "http://localhost:5173"

    def resolve_auth_headers() -> dict:
        return {}

    def get_auth_headers_for_index(n: int) -> dict:
        if n == 1:
            key = os.environ.get("VIBECHECK_API_KEY", "").strip()
            if not key:
                key = _read_vibecheck_config("api_key")
        else:
            key = os.environ.get(f"VIBECHECK_API_KEY_{n}", "").strip()
            if not key:
                key = _read_vibecheck_config(f"api_key_{n}")
        return {"Authorization": f"Bearer {key}"} if key else {}

    def log_hook_issue(script: str, message: str, exc: Exception | None = None) -> None:
        try:
            note = f"[{script}] {message}"
            if exc:
                note += f" | {type(exc).__name__}: {exc}"
            print(note, file=sys.stderr)
        except Exception:
            return


def _post_to_targets(path: str, payload: dict, timeout: int = 5) -> dict:
    """POST payload to all configured targets. Returns primary response."""
    targets = get_api_targets()
    data = json.dumps(payload, default=str).encode()
    primary_response: dict = {"error": "primary target unreachable"}

    for n, target_url in enumerate(targets, start=1):
        auth_headers: dict = {}
        try:
            auth_headers = get_auth_headers_for_index(n)
        except Exception:
            pass
        try:
            req = urllib_request.Request(
                f"{target_url}{path}",
                data=data,
                headers={"Content-Type": "application/json", **auth_headers},
                method="POST",
            )
            with urllib_request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                response = json.loads(body) if body else {"ok": True}
                if n == 1:
                    primary_response = response
        except (URLError, OSError, Exception) as e:
            label = "primary" if n == 1 else f"secondary target {n}"
            log_hook_issue("vibecheck-mcp", f"Fan-out to {label} failed: POST {path}", e)

    return primary_response


def post_dismiss_issue(issue_id: str, resolution_note: str = "") -> dict:
    """POST a dismiss-issue request and return server result (fan-out to all targets)."""
    session_id, cwd = _get_session_context()
    payload = {
        "session_id": session_id,
        "cwd": cwd,
        "issue_id": issue_id,
        "resolution_note": resolution_note,
    }
    result = _post_to_targets("/api/push/dismiss-issue", payload, timeout=5)
    if not result.get("ok") and "dismissed" not in result:
        return {"ok": False, "dismissed": 0}
    return result


def post_begin_completion(objective_id: str = "", trigger: str = "manual") -> dict:
    """POST begin-completion handshake to all targets; return primary response (contains blocked state)."""
    session_id, cwd = _get_session_context()
    payload = {
        "session_id": session_id,
        "cwd": cwd,
        "objective_id": objective_id,
        "trigger": trigger,
    }
    result = _post_to_targets("/api/push/begin-completion", payload, timeout=8)
    if result.get("error"):
        return {"ok": False, "blocked": True, "reason": "begin-completion request failed"}
    return result


def post_finalize_objective(objective_id: str = "", checkpoint_summary: str = "") -> dict:
    """POST finalize-objective to all targets; return primary response (contains blocked state)."""
    session_id, cwd = _get_session_context()
    payload = {
        "session_id": session_id,
        "cwd": cwd,
        "objective_id": objective_id,
        "checkpoint_summary": checkpoint_summary,
    }
    result = _post_to_targets("/api/push/finalize-objective", payload, timeout=8)
    if result.get("error"):
        return {"ok": False, "blocked": True, "reason": "finalize-objective request failed"}
    return result


def _api_call(method: str, path: str, payload: dict | None = None, timeout: int = 8) -> dict:
    """Make an HTTP call to the VibeCheck API and return JSON response.

    POST/PUT/PATCH writes fan-out to all configured targets (primary response returned).
    GET/DELETE stay single-target (reads and session lookups).
    """
    if method in ("POST", "PUT", "PATCH") and payload is not None:
        return _post_to_targets(path, payload, timeout=timeout)

    # GET/DELETE: single-target only
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


def post_mcp_report(report_data: dict) -> dict:
    """POST an MCPReport to all configured targets. Returns primary response."""
    return _post_to_targets("/api/push/mcp-report", report_data, timeout=5)


def _resolve_session_id() -> str:
    """Resolve the current session_id via PPID lookup.

    Claude Code spawns MCP servers as direct children (confirmed via empirical
    test: hook PPID == MCP server PPID == Claude Code PID). The SessionStart
    hook registers this mapping in the DB; we look it up on every tool call.

    No in-process cache by design: re-reading on every call ensures /clear and
    /compact (which issue a new session_id) are picked up immediately on the
    next invocation without any staleness window.

    Fallback chain:
      1. PPID lookup via /api/session-by-ppid/{ppid}  (preferred, concurrent-safe)
      2. CLAUDE_SESSION_ID env var                     (may be "unknown" in MCP envs)
      3. CLAUDE_CODE_SESSION_ID env var                (available in v2.1.49+ on some configs)
      4. "unknown"
    """
    try:
        ppid = os.getppid()
        result = _api_call("GET", f"/api/session-by-ppid/{ppid}", timeout=2)
        resolved = result.get("session_id")
        if resolved and resolved != "unknown":
            return resolved
    except Exception:
        pass
    # Fallback: env vars (usually "unknown" in MCP server processes, but try anyway)
    for env_var in ("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        val = os.environ.get(env_var, "")
        if val and val != "unknown":
            return val
    return "unknown"


def _get_session_context() -> tuple[str, str]:
    """Return (session_id, cwd). session_id via PPID lookup; cwd from env."""
    return _resolve_session_id(), os.environ.get("CLAUDE_CWD", os.getcwd())


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
                "primary reporting tool — use it continuously, not just at the end. "
                "If this step involved a non-obvious choice — one that a future engineer "
                "couldn't reconstruct from the code alone — set decision_signal.decided "
                "to a brief description of what was chosen, and decision_signal.why to "
                "the reasoning if you have it. Keep it short; the server will enrich it."
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
                    "decision_signal": {
                        "type": "object",
                        "description": (
                            "Set when this checkpoint involved a non-obvious choice that "
                            "a future engineer couldn't reconstruct from the code alone. "
                            "Ask yourself: would someone else possibly need to know this "
                            "to do future work? If yes, capture it here."
                        ),
                        "properties": {
                            "decided": {
                                "type": "string",
                                "description": "One sentence: what was chosen",
                            },
                            "why": {
                                "type": "string",
                                "description": "Brief reasoning (optional — server will enrich)",
                            },
                        },
                        "required": ["decided"],
                    },
                },
                "required": ["status_label", "summary"],
            },
        ),
        types.Tool(
            name="vibecheck_resolve",
            description=(
                "Resolve a context (issue, spec, etc.) in the VibeCheck dashboard. "
                "Use this after fixing a blocking issue from /vibecheck:review, or after "
                "completing a spec. Accepts either the UUID returned by vc-review or the "
                "ISS-XX label shown on the dashboard. Type-aware: issues are archived, "
                "specs are marked implemented."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": (
                            "The context ID to resolve. Accepts the UUID from vc-review "
                            "(e.g. '3f8a...') or the ISS-XX label (e.g. 'ISS-33'). "
                            "Use the label or UUID exactly as returned — do not guess."
                        ),
                    },
                    "note": {
                        "type": "string",
                        "description": "Brief description of how the issue was resolved",
                    },
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="vibecheck_begin_completion",
            description=(
                "Step 1 of 2 in the completion protocol. Call this when you have "
                "finished implementing a task and are ready for final review. "
                "Returns the list of files to review. After reviewing, call "
                "vibecheck_finalize_objective to close out. "
                "Note: /vibecheck:complete runs this full workflow automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "objective_id": {
                        "type": "string",
                        "description": "Objective ID to complete (omit to use the active objective)",
                    },
                },
            },
        ),
        types.Tool(
            name="vibecheck_finalize_objective",
            description=(
                "Step 2 of 2 in the completion protocol. Call this after you have "
                "reviewed the files returned by vibecheck_begin_completion and "
                "resolved any issues. Marks the objective as complete on the dashboard."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "objective_id": {
                        "type": "string",
                        "description": "Objective ID to finalize (omit to use the active objective)",
                    },
                    "checkpoint_summary": {
                        "type": "string",
                        "description": "1-2 sentence summary of what was completed",
                    },
                },
            },
        ),
        # ── Context Library tools ────────────────────────────────────────────
        types.Tool(
            name="vibecheck_list_contexts",
            description=(
                "List contexts from the VibeCheck Context Library. Returns id, title, type, status, and brief preview for each context. "
                "Use this to find specs to implement, issues to fix, or decisions to reference. "
                "By default returns all statuses except archived — draft, active, implemented, resolved, and open contexts are all visible. "
                "Pass status= to filter to a specific status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["research", "spec", "issue", "decision", "note", "standard", "skill", "persona"],
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
                "Get detail for a context. By default returns full content including brief, "
                "status history, and linked sessions. Set summary_only=True for tier-2 "
                "progressive reveal: returns title, type, status, and context_summary only "
                "(no brief). Use summary_only after vibecheck_discover to evaluate a match "
                "before loading full content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Context ID",
                    },
                    "summary_only": {
                        "type": "boolean",
                        "description": "If true, return title + context_summary only (no brief). Default false.",
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
                        "enum": ["research", "spec", "issue", "decision", "note", "standard", "skill", "persona"],
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
                    "context_summary": {
                        "type": "string",
                        "description": "For type=skill: short trigger condition (1-2 sentences). This is what gets embedded for discovery.",
                    },
                    "skill_allowed_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "For type=skill: optional list of tool names this skill is allowed to use",
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
                    "context_summary": {
                        "type": "string",
                        "description": (
                            "For skill-type contexts: the situational trigger condition — "
                            "describe WHEN this cognitive mode should activate (work phase, "
                            "what the agent has just done, the specific signal). "
                            "For other types: a one-sentence knowledge summary for embedding."
                        ),
                    },
                    "source_snapshot": {
                        "type": "object",
                        "description": "Replace source metadata (e.g. issue severity, location)",
                    },
                    "status": {
                        "type": "string",
                        "description": (
                            "New status. Valid values depend on context type: "
                            "issues: open, dispatched, resolved, deferred, archived. "
                            "Specs/research: draft, shaped, ready, dispatched, implemented, deferred, archived. "
                            "Decisions/standards: draft, active, archived."
                        ),
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
                "Manually link the current session to a context. Most tools "
                "(vibecheck_get_context, vibecheck_update_context, vibecheck_implement) "
                "link automatically — use this only when you need to explicitly record "
                "that a context is relevant to this session without reading or updating it."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "context_id": {
                        "type": "string",
                        "description": "Context ID (UUID or label, e.g. 'SPEC-4' or 'ISS-12')",
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
        types.Tool(
            name="vibecheck_discover",
            description=(
                "Discover relevant contexts (skills, decisions, standards, research) from the "
                "VibeCheck Context Library using hybrid BM25+vector scoring. Call before "
                "starting any non-trivial task to surface relevant methodology, prior decisions, "
                "or research. Returns a ranked list of matches — use vibecheck_get_context with "
                "summary_only=True to evaluate a match, or vibecheck_get_context to load full "
                "content. For skills specifically, pass layer='skill'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What you are currently working on or looking for (1-2 sentences)",
                    },
                    "layer": {
                        "type": "string",
                        "enum": ["skill", "standard", "decision", "work"],
                        "description": "Filter by layer. Omit to search all layers.",
                    },
                    "type": {
                        "type": "string",
                        "description": "Filter by context type (skill, decision, standard, research, spec, etc.)",
                    },
                    "repo_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Repo/tech tags to augment query matching",
                    },
                    "situation": {
                        "type": "string",
                        "description": "What you are currently doing in 1-2 sentences — the specific problem or moment. Used to sharpen relevance matching independently of session_id resolution. Example: 'Debugging a race condition in the coverage aggregator after a server restart.'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 5)",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="vibecheck_implement",
            description=(
                "Begin implementing a spec or research context from the Context Library. "
                "Loads the full active context set (spec brief, related decisions, standing "
                "standards) and links the current session to the spec as 'dispatched'. "
                "Call this at the start of implementing a spec. When done, call "
                "vibecheck_resolve with the spec ID to mark it implemented."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Spec context ID (UUID or label, e.g. 'SPEC-4' or a UUID)",
                    },
                },
                "required": ["id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    global _EVENT_SEQ
    session_id, cwd = _get_session_context()

    # vibecheck_resolve — type-aware resolution, accepts UUID or ISS-XX label
    if name == "vibecheck_resolve":
        ctx_id = arguments.get("id", "")
        note = arguments.get("note", "")
        result = post_dismiss_issue(ctx_id, note)
        dismissed = int(result.get("dismissed", 0) or 0) if isinstance(result, dict) else 0
        note_suffix = f" ({note})" if note else ""
        if dismissed > 0:
            # Auto-link: resolving an issue records which session fixed it
            if session_id and session_id != "unknown":
                try:
                    # Resolve label → canonical UUID first (label lookup in GET endpoint)
                    resolved_ctx = _api_call("GET", f"/api/contexts/{url_quote(ctx_id, safe='')}")
                    canonical_id = resolved_ctx.get("id") if resolved_ctx and not resolved_ctx.get("error") else None
                    if canonical_id:
                        _api_call("POST", f"/api/contexts/{canonical_id}/link-session", {
                            "session_id": session_id,
                            "link_type": "issue_resolved",
                        })
                except Exception:
                    pass
            text = f"Resolved {ctx_id} in VibeCheck{note_suffix}."
        else:
            text = f"Could not resolve {ctx_id} — no matching active context found{note_suffix}."
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
            label = c.get("label", "")
            id_str = f"{label} / {c['id']}" if label else c["id"]
            lines.append(f"- [{c['type']}] **{c['title']}** ({status}) id={id_str}\n  {preview}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "vibecheck_get_context":
        ctx_id = url_quote(arguments.get("id", ""), safe="")
        summary_only = arguments.get("summary_only", False)
        url_suffix = "?summary_only=true" if summary_only else ""
        result = _api_call("GET", f"/api/contexts/{ctx_id}{url_suffix}")
        if result.get("error") or not result.get("id"):
            return [types.TextContent(type="text", text=f"Context not found: {ctx_id}")]

        # Auto-link: reading a context during a session creates a "read_in" link
        if not summary_only and session_id and session_id != "unknown":
            try:
                _api_call("POST", f"/api/contexts/{result['id']}/link-session", {
                    "session_id": session_id,
                    "link_type": "read_in",
                })
            except Exception:
                pass

        label = result.get("label")
        heading = f"{label} — {result['title']}" if label else result["title"]
        lines = [
            f"# {heading}",
            f"**Type:** {result['type']} | **Status:** {result['status']} | **Layer:** {result.get('layer', '')}",
        ]
        if result.get("tags"):
            lines.append(f"**Tags:** {', '.join(result['tags'])}")

        if summary_only:
            summary = result.get("context_summary") or "(no summary yet)"
            lines.append(f"\n**Summary:** {summary}")
            lines.append("\n*Use vibecheck_get_context(id) to load the full brief.*")
        else:
            if result.get("predecessor_id"):
                lines.append(f"**Predecessor:** {result['predecessor_id']}")
            if result.get("successor_ids"):
                lines.append(f"**Successors:** {', '.join(result['successor_ids'])}")
            lines.append(f"\n## Brief\n{result.get('brief', '(empty)')}")

            # Session evidence section
            se = result.get("session_evidence")
            if se is not None:
                sess_list = se.get("sessions", [])
                lookback = se.get("lookback_days", 30)
                if sess_list:
                    lines.append(f"\n## Session Evidence")
                    gold_silver = [s for s in sess_list if s.get("match_tier") in ("gold", "silver")]
                    bronze = [s for s in sess_list if s.get("match_tier") == "bronze"]
                    if gold_silver:
                        lines.append("**Verified connections:**")
                        for s in gold_silver:
                            note = f" ⚠ {s['evidence_note']}" if s.get("evidence_note") else ""
                            via = s.get("match_via") or []
                            via_str = f" ↳ Linked via [{', '.join(via)}]" if via else " ↳ Linked"
                            title = s.get("objective_title") or s.get("session_id", "")
                            lines.append(f"- {title}{note}{via_str}")
                    if bronze:
                        lines.append("**Related:**")
                        for s in bronze:
                            note = f" ⚠ {s['evidence_note']}" if s.get("evidence_note") else ""
                            title = s.get("objective_title") or s.get("session_id", "")
                            lines.append(f"- {title}{note}")
                else:
                    lines.append(f"\n*0 sessions touched this in the last {lookback} days.*")

        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "vibecheck_discover":
        query = arguments.get("query", "").strip()
        if not query:
            return [types.TextContent(type="text", text="Error: query is required.")]
        layer = arguments.get("layer", "")
        ctx_type = arguments.get("type", "")
        situation = (arguments.get("situation") or "").strip()
        repo_tags = arguments.get("repo_tags", [])
        repo_tags_str = ",".join(repo_tags) if repo_tags else ""
        # Layer-specific default limits: skills max 2, decisions max 5
        _layer_limits = {"skill": 2, "decision": 5}
        requested_limit = arguments.get("limit", _layer_limits.get(layer, 5))
        limit = min(int(requested_limit), _layer_limits.get(layer, 20))
        params = f"q={url_quote(query)}&limit={limit}"
        if layer:
            params += f"&layer={url_quote(layer)}"
        if ctx_type:
            params += f"&type={url_quote(ctx_type)}"
        if repo_tags_str:
            params += f"&repo_tags={url_quote(repo_tags_str)}"
        # Pass session_id for context-enriched scoring and why_now generation
        if session_id and session_id != "unknown":
            params += f"&session_id={url_quote(session_id)}"
        # Pass explicit situation to sharpen matching (works even without session_id)
        if situation:
            params += f"&situation={url_quote(situation)}"
        result = _api_call("GET", f"/api/contexts/discover?{params}")
        if result.get("error"):
            return [types.TextContent(type="text", text=f"Discovery failed: {result['error']}")]
        contexts = result.get("contexts", [])
        situation_read = result.get("situation_read")
        excluded_count = result.get("excluded_count", 0)
        session_enriched = result.get("session_enriched", False)
        if not contexts:
            lines = ["**No high-confidence contexts found.**"]
            if situation_read:
                lines.append(f"\n*Situation: {situation_read}*")
            if excluded_count:
                lines.append(f"*{excluded_count} previously-loaded context(s) filtered out (already in your context window).*")
            lines.append("\nBroaden your query or call without a layer filter to search all layers.")
            return [types.TextContent(type="text", text="\n".join(lines))]
        # Build response header
        lines = []
        if situation_read and session_enriched:
            lines.append(f"## What applies to your situation\n")
            lines.append(f"*{situation_read}*\n")
            if excluded_count:
                lines.append(f"*({excluded_count} previously-loaded context(s) filtered out — already in your context window.)*\n")
        else:
            layer_label = f" [{layer}]" if layer else ""
            lines.append(f"## Relevant Contexts{layer_label}\n")
        # Format each result
        for c in contexts:
            label = c.get("label", "")
            layer_str = c.get("layer", "")
            type_str = c.get("type", "")
            heading = f"{c['title']} ({label})" if label else c["title"]
            layer_tag = f"[{layer_str}] " if layer_str and not layer else ""
            lines.append(f"### {layer_tag}{heading}")
            if c.get("context_summary"):
                lines.append(f"> {c['context_summary']}\n")
            if c.get("why_now"):
                lines.append(f"**Why now:** {c['why_now']}")
            if type_str == "skill":
                lines.append(f"*Activate with: `vibecheck_get_context(\"{c.get('id', label)}\")` then follow the brief.*")
            lines.append("")
        # Session history section
        session_matches = result.get("session_matches", [])
        if session_matches:
            lines.append("## Session History")
            verified = [s for s in session_matches if s.get("match_tier") in ("gold", "silver")]
            related = [s for s in session_matches if s.get("match_tier") == "bronze"]
            if verified:
                lines.append("**Verified connections:**")
                for s in verified:
                    note = f" ⚠ {s['evidence_note']}" if s.get("evidence_note") else ""
                    via = s.get("match_via") or []
                    via_str = f" ↳ Linked via [{', '.join(str(v) for v in via)}]" if via else ""
                    title = s.get("objective_title") or s.get("session_id", "")
                    lines.append(f"- {title}{note}{via_str}")
            if related:
                lines.append("**Related:**")
                for s in related:
                    note = f" ⚠ {s['evidence_note']}" if s.get("evidence_note") else ""
                    title = s.get("objective_title") or s.get("session_id", "")
                    lines.append(f"- {title}{note}")
            lines.append("")

        # Single CTA
        lines.append("---")
        lines.append("Evaluate a match: `vibecheck_get_context(id, summary_only=True)` · Load full brief: `vibecheck_get_context(id)`")
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
        if arguments.get("context_summary"):
            payload["context_summary"] = arguments["context_summary"]
        if arguments.get("skill_allowed_tools"):
            payload["skill_allowed_tools"] = arguments["skill_allowed_tools"]
        result = _api_call("POST", "/api/contexts", payload)
        if result.get("error"):
            return [types.TextContent(type="text", text=f"Failed to create context: {result['error']}")]

        # Link the new context to the current session
        ctx_id = result.get("id")
        if ctx_id and session_id and session_id != "unknown":
            # Issues get a distinct link_type so they surface in the Issues section
            auto_link_type = "issue_created" if arguments.get("type") == "issue" else "created_in"
            _api_call("POST", f"/api/contexts/{ctx_id}/link-session", {
                "session_id": session_id,
                "link_type": auto_link_type,
            })

        label = result.get("label", "")
        id_str = f"{label} / {result.get('id', '')}" if label else result.get("id", "")
        ctx_type = result.get("type", "note")
        title = result.get("title", "")

        if ctx_type == "decision" and label:
            url = f"{get_frontend_url()}/#context/{label}"
            text = (
                f"Decision logged to Context Library: \"{title}\" ({label})\n"
                f"View: {url}\n"
                f"*Tell the developer: \"I documented this decision as {label} in VibeCheck.\"*"
            )
        else:
            text = f"Context created: [{ctx_type}] \"{title}\" (id={id_str})"

        return [types.TextContent(type="text", text=text)]

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
        if arguments.get("context_summary") is not None:
            patch["context_summary"] = arguments["context_summary"]
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
            patch_result = _api_call("PATCH", f"/api/contexts/{ctx_id}", patch)
            if patch_result.get("error"):
                return [types.TextContent(
                    type="text",
                    text=f"Failed to update context: {patch_result['error']}",
                )]

        # Handle status change (separate endpoint with state machine)
        if arguments.get("status"):
            evidence = {}
            if arguments.get("notes"):
                evidence["notes"] = arguments["notes"]
            status_result = _api_call("POST", f"/api/contexts/{ctx_id}/status", {
                "status": arguments["status"],
                "source": "explicit",
                "evidence": evidence if evidence else None,
            })
            if status_result.get("error"):
                return [types.TextContent(
                    type="text",
                    text=f"Status change failed: {status_result['error']}",
                )]

        # Fetch updated — do this first so we have the canonical UUID for the session link
        result = _api_call("GET", f"/api/contexts/{ctx_id}")
        if result.get("error") or not result.get("id"):
            return [types.TextContent(type="text", text=f"Context not found: {ctx_id}")]

        # Auto-link: use result['id'] (canonical UUID) not ctx_id (may be a label like ISS-42)
        if session_id and session_id != "unknown":
            try:
                _api_call("POST", f"/api/contexts/{result['id']}/link-session", {
                    "session_id": session_id,
                    "link_type": "worked_on",
                })
            except Exception:
                pass

        return [types.TextContent(
            type="text",
            text=f"Context updated: \"{result['title']}\" — status={result['status']}",
        )]

    if name == "vibecheck_link_context":
        ctx_id = url_quote(arguments.get("context_id", ""), safe="")
        result = _api_call("POST", f"/api/contexts/{ctx_id}/link-session", {
            "session_id": session_id,
            "link_type": "worked_on",
        })
        if result.get("error"):
            return [types.TextContent(type="text", text=f"Link failed: {result['error']}")]
        return [types.TextContent(type="text", text=f"Session linked to context {ctx_id}.")]

    if name == "vibecheck_find_related":
        query = arguments.get("query", "")
        layer = arguments.get("layer", "decision")
        limit = arguments.get("limit", 5)
        result = _api_call("GET", f"/api/contexts/related?q={url_quote(query)}&layer={layer}&limit={limit}&include_counts=true")
        related = result.get("related", [])
        if not related:
            return [types.TextContent(type="text", text="No related contexts found.")]

        # Auto-link top result if high confidence
        if (
            len(related) > 0
            and related[0].get("similarity", 0) >= 0.80
            and session_id
            and session_id != "unknown"
        ):
            try:
                top_id = related[0].get("id")
                if top_id:
                    _api_call("POST", f"/api/contexts/{url_quote(top_id, safe='')}/link-session", {
                        "session_id": session_id,
                        "link_type": "read_in",
                    })
            except Exception:
                pass

        lines = []
        for r in related:
            sim = r.get("similarity", 0)
            brief = (r.get("brief", "") or "")[:200]
            count_str = ""
            if r.get("linked_session_count") is not None:
                count_str = f" · {r['linked_session_count']} session(s)"
            lines.append(f"- [{r['type']}] **{r['title']}** (similarity={sim:.2f}{count_str}) id={r['id']}\n  {brief}")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "vibecheck_get_active_context_set":
        ctx_id = url_quote(arguments.get("context_id", ""), safe="")
        result = _api_call("GET", f"/api/contexts/active-set?context_id={ctx_id}")
        if result.get("error"):
            return [types.TextContent(type="text", text=f"Failed to load active context set: {result['error']}")]

        # Auto-link: link the work context, all injected standards, and semantic decisions as "read_in"
        if session_id and session_id != "unknown" and arguments.get("context_id"):
            ctx_ids_to_link = []
            raw_work_id = result.get("work", {}).get("id") or arguments["context_id"]
            ctx_ids_to_link.append(raw_work_id)
            for s in result.get("standards", []):
                if s.get("id"):
                    ctx_ids_to_link.append(s["id"])
            for d in result.get("decisions", []):
                if d.get("id"):
                    ctx_ids_to_link.append(d["id"])
            for ctx_id_to_link in ctx_ids_to_link:
                try:
                    _api_call("POST", f"/api/contexts/{url_quote(ctx_id_to_link, safe='')}/link-session", {
                        "session_id": session_id,
                        "link_type": "read_in",
                    })
                except Exception:
                    pass
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
        skill_lib = result.get("skill_library")
        if skill_lib:
            lines.append("## Skill Library")
            lines.append(
                f"{skill_lib['count']} active skill(s): {skill_lib['titles']}.\n"
                "Before starting any non-trivial task, call `vibecheck_discover(query=..., layer=\"skill\")` "
                "to surface relevant methodology."
            )
            lines.append("")
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name == "vibecheck_implement":
        raw_id = arguments.get("id", "")
        ctx_id = url_quote(raw_id, safe="")
        ctx = _api_call("GET", f"/api/contexts/{ctx_id}")
        if ctx.get("error") or not ctx.get("id"):
            return [types.TextContent(type="text", text=f"Context not found: {raw_id}")]

        # Link current session as dispatched
        if session_id and session_id != "unknown":
            _api_call("POST", f"/api/contexts/{ctx['id']}/link-session", {
                "session_id": session_id,
                "link_type": "dispatched",
            })
            # Transition status to dispatched if currently ready/shaped
            if ctx.get("status") in ("ready", "shaped", "draft"):
                _api_call("POST", f"/api/contexts/{ctx['id']}/status", {
                    "status": "dispatched",
                    "source": "explicit",
                    "evidence": {"notes": "Implementation started via vibecheck_implement"},
                })

        # Load full active context set
        active = _api_call("GET", f"/api/contexts/active-set?context_id={ctx_id}")

        label = ctx.get("label", "")
        resolve_id = label or ctx["id"]
        heading = f"{label} — {ctx['title']}" if label else ctx["title"]
        lines = [
            f"# Implementing: {heading}",
            f"**Type:** {ctx['type']} | **Status:** {ctx['status']} | **Layer:** {ctx['layer']}",
            "",
            f"## Spec Brief\n{ctx.get('brief') or '(no brief — use vibecheck_update_context to add one)'}",
        ]
        decisions = (active.get("decisions") or [])
        if decisions:
            lines.append("\n## Relevant Past Decisions")
            for d in decisions:
                brief = (d.get("brief") or "")[:400]
                lbl = f" ({d['label']})" if d.get("label") else ""
                lines.append(f"### {d['title']}{lbl}\n{brief}\n")
        standards = (active.get("standards") or [])
        if standards:
            lines.append("\n## Standing Standards")
            for s in standards:
                lines.append(f"### {s['title']}\n{s.get('brief', '')}\n")
        skill_lib = active.get("skill_library")
        if skill_lib:
            lines.append("\n## Skill Library")
            lines.append(
                f"{skill_lib['count']} active skill(s): {skill_lib['titles']}.\n"
                "Call `vibecheck_discover(query=..., layer=\"skill\")` before starting work."
            )
        lines.append(f"\n---\nWhen implementation is complete, call `vibecheck_resolve` with `id=\"{resolve_id}\"` to mark this spec as implemented.")
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

    mcp_result = post_mcp_report(report)

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
        "vibecheck_begin_completion": "Completion protocol started.",
        "vibecheck_finalize_objective": "Objective finalize requested.",
    }
    msg = ack_messages.get(name, "Reported to VibeCheck.")

    # Surface ambient context suggestion if VibeCheck detected one
    if name == "vibecheck_update" and isinstance(mcp_result, dict):
        # Decision logged inline — tell the developer
        logged = mcp_result.get("logged_decision")
        if logged and logged.get("label"):
            label = logged["label"]
            title = logged.get("title", "")
            url = f"{get_frontend_url()}/#context/{label}"
            lines = [msg, f"\nLogged to Context Library: **{title}** ({label})"]
            lines.append(f"View: {url}")
            lines.append(f"*Tell the developer: \"I documented this decision as {label} in VibeCheck.\"*")
            msg = "\n".join(lines)

        # Server-initiated context notifications (auto-mined decisions, Phase 2: issues, etc.)
        pending = mcp_result.get("pending_notifications") or []
        for notif in pending:
            notif_label = notif.get("label", "")
            notif_title = notif.get("title", "")
            notif_type = notif.get("ctx_type", "context")
            if notif_label and notif_title:
                notif_url = f"{get_frontend_url()}/#context/{notif_label}"
                lines = [
                    msg,
                    f"\nAuto-logged to Context Library: **{notif_title}** ({notif_label}) [{notif_type}]",
                    f"View: {notif_url}",
                    f"*Tell the developer: \"VibeCheck auto-logged a {notif_type} as {notif_label}.\"*",
                ]
                msg = "\n".join(lines)

        # Ambient context suggestion
        suggestion = mcp_result.get("suggested_context")
        if suggestion and suggestion.get("title"):
            ctx_id = suggestion.get("label") or suggestion.get("id", "")
            lines = [
                msg,
                f"\nVibeCheck surfaced a relevant {suggestion.get('layer', 'context')}: "
                f"{suggestion['title']} ({ctx_id})",
            ]
            if suggestion.get("context_summary"):
                lines.append(f"> {suggestion['context_summary']}")
            if suggestion.get("why_now"):
                lines.append(f"Why now: {suggestion['why_now']}")
            if ctx_id:
                lines.append(f'Load with: vibecheck_get_context("{ctx_id}")')
            msg = "\n".join(lines)

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
