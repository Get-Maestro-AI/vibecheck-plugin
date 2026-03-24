#!/usr/bin/env python3
"""Context injection hook for UserPromptSubmit.

Runs SYNCHRONOUSLY on every UserPromptSubmit — stdout is visible to Claude
before it processes the user's message.

Two-pass discovery (SPEC-149 Phase 5):
  Pass 1 — Skills (layer=skill): "What should I *do*?"
  Pass 2 — General (all layers): "What should I *know*?"
This ensures skills are never crowded out by standards or decisions.

Query preprocessing (SPEC-149 Phase 3):
  Strips conversational filler before discovery to improve BM25 precision.

Plan suggestion (SPEC-177):
  Checks /api/plan-context — if a fresh objective (< 10 min) has no active
  plan, surfaces a one-time suggestion to run /vibecheck:plan.

Uses only stdlib. Always exits 0. Targets < 3s wall time.
"""
from __future__ import annotations
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as urllib_request
from urllib import parse as urllib_parse
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import resolve_auth_headers  # type: ignore[import]
from lib.config import get_api_url          # type: ignore[import]

# Prompts shorter than this are likely one-word replies or continuations.
_MIN_PROMPT_LEN = 15

# Prompt prefixes that indicate a short continuation — skip injection for these.
_SKIP_PREFIXES = (
    "yes", "no", "ok", "okay", "sure", "thanks", "thank you",
    "got it", "sounds good", "looks good", "good", "great", "perfect",
    "continue", "go ahead", "do it", "proceed", "keep going",
    "agreed", "correct", "right", "exactly", "yep", "nope",
)

# Max characters of the prompt to use as the search query.
_QUERY_MAX_CHARS = 400

# HTTP timeout per request — tight to avoid blocking Claude's response.
_HTTP_TIMEOUT = 1.8

# Shorter timeout for the plan suggestion check — it's optional and lower priority.
_PLAN_SUGGESTION_TIMEOUT = 0.8

# Local cache file: records objective IDs that have already received a suggestion.
_PLAN_SUGGESTION_CACHE = Path.home() / ".vibecheck" / "plan_suggested.json"

# Local cache file: records session IDs that have already received a workflow nudge.
_WORKFLOW_NUDGE_CACHE = Path.home() / ".vibecheck" / "workflow_nudged.json"

# Pending echoes from capture_artifact.py — PostToolUse stdout isn't reliably
# visible to the user, so we relay stashed echoes on the next UserPromptSubmit.
_PENDING_ECHOES = Path.home() / ".vibecheck" / ".pending_echoes"

# Regex matching action-verb prompts that signal "I'm about to build something".
_TASK_INTENT_RE = re.compile(
    r"^\s*(build|add|implement|create|make|write|fix|refactor)\b",
    re.IGNORECASE,
)

# ── Correction signal detection (SPEC-322) ───────────────────────────────────
# Patterns that indicate the user is correcting a convention or preference.
# Deliberately specific to avoid false positives on casual phrases like
# "never mind" or "don't worry about it".
_CORRECTION_PATTERNS = [
    # "I don't use X" / "we don't use X"
    re.compile(r"\b(?:I|we)\s+don'?t\s+use\b", re.IGNORECASE),
    # "never use/run/call/execute/do/write/commit X"
    re.compile(
        r"\bnever\s+(?:use|run|call|execute|do|write|apply|add|push|deploy|commit)\b",
        re.IGNORECASE,
    ),
    # "always use X"
    re.compile(r"\balways\s+use\b", re.IGNORECASE),
    # "we always use/run/do X"
    re.compile(
        r"\bwe\s+always\s+(?:use|run|do|write|call|prefer|go\s+with)\b",
        re.IGNORECASE,
    ),
    # "I've told you" / "I've said this" / "I've mentioned this" / "I've already said"
    re.compile(
        r"\bI'?ve\s+(?:told\s+you|said\s+this|mentioned\s+this|already\s+said)\b",
        re.IGNORECASE,
    ),
    # "stop using/running/calling X"
    re.compile(r"\bstop\s+(?:using|running|calling|doing)\b", re.IGNORECASE),
    # "use X, not Y" / "use X not Y"
    re.compile(r"\buse\s+\w[\w\s]{0,20},?\s+not\b", re.IGNORECASE),
    # "don't use/run/call/execute/commit X"
    re.compile(
        r"\bdon'?t\s+(?:use|run|call|execute|push|commit|write)\b",
        re.IGNORECASE,
    ),
]

# Two-pass discovery limits.
_SKILL_LIMIT = 3
_GENERAL_LIMIT = 2

# ── Phase 3: Query preprocessing ────────────────────────────────────────────

# Conversational filler prefixes to strip (case-insensitive).
_FILLER_PREFIXES = [
    r"^i would like you to\s+",
    r"^i want you to\s+",
    r"^i'd like you to\s+",
    r"^i need you to\s+",
    r"^can you (please\s+)?",
    r"^could you (please\s+)?",
    r"^please\s+",
    r"^let'?s (first\s+|go ahead and\s+|start by\s+)?",
    r"^now\s+",
    r"^next\s+",
    r"^first\s+",
    r"^go ahead and\s+",
]
_FILLER_RE = re.compile("|".join(_FILLER_PREFIXES), re.IGNORECASE)

# Mid-sentence filler to strip.
_MID_FILLER = [
    r"\bwhat we just built\b",
    r"\bwhat we've built\b",
    r"\bwhat was just built\b",
    r"\bthe changes we made\b",
    r"\bthe code we wrote\b",
]
_MID_FILLER_RE = re.compile("|".join(_MID_FILLER), re.IGNORECASE)


def _preprocess_query(prompt: str) -> str:
    """Strip conversational filler to extract core intent for BM25."""
    q = prompt.strip()
    # Strip leading filler (may need multiple passes for chained prefixes).
    for _ in range(3):
        q_new = _FILLER_RE.sub("", q).strip()
        if q_new == q:
            break
        q = q_new
    # Strip mid-sentence filler.
    q = _MID_FILLER_RE.sub("", q).strip()
    # Collapse whitespace.
    q = re.sub(r"\s+", " ", q).strip(" .,;:")
    # If preprocessing stripped too much, fall back to original.
    if len(q) < 8:
        return prompt.strip()[:_QUERY_MAX_CHARS]
    return q[:_QUERY_MAX_CHARS]


def _should_skip(prompt: str) -> bool:
    """Return True if the prompt is too short or a plain continuation."""
    stripped = prompt.strip()
    if len(stripped) < _MIN_PROMPT_LEN:
        return True
    lower = stripped.lower().rstrip(".")
    for prefix in _SKIP_PREFIXES:
        if lower == prefix or lower.startswith(prefix + " "):
            return True
    return False


def _discover(api_url: str, auth_headers: dict, query: str,
              situation: str, session_id: str,
              layer: str | None = None, limit: int = 4) -> list[dict]:
    """Call the discover endpoint. Returns list of context dicts or []."""
    qs: dict = {"q": query, "situation": situation, "limit": limit}
    if session_id and session_id != "unknown":
        qs["session_id"] = session_id
    if layer:
        qs["layer"] = layer

    url = f"{api_url}/api/contexts/discover?{urllib_parse.urlencode(qs)}"
    req = urllib_request.Request(url, headers={"Accept": "application/json", **auth_headers})

    with urllib_request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data.get("contexts", [])


def _format_brief(contexts: list[dict]) -> str:
    """Format discovered contexts as a concise brief Claude will act on."""
    lines = ["[VibeCheck] Relevant context for this task:\n"]
    skill_labels: list[str] = []
    for c in contexts:
        label = c.get("label", "")
        title = c.get("title", "")
        layer = c.get("layer", "")
        if layer == "skill" and label:
            skill_labels.append(label)

        heading = f"{title} ({label})" if label else title
        layer_tag = f"[{layer}] " if layer else ""
        lines.append(f"  • {layer_tag}{heading}")

        summary = (c.get("context_summary") or "").strip()
        if summary:
            lines.append(f"    {summary}")

        why = (c.get("why_now") or "").strip()
        if why:
            lines.append(f"    → {why}")

        lines.append("")

    if skill_labels:
        calls = " and ".join(f'vibecheck_get_context("{lbl}")' for lbl in skill_labels)
        lines.append(
            f"  Non-negotiable if relevant: for any [skill] above that applies to your\n"
            f"  current task, load its full brief first and follow its methodology before\n"
            f"  responding. Do NOT start work first.\n"
            f"  Load: {calls}"
        )
    else:
        lines.append(
            "  Load any context in full with: "
            'vibecheck_get_context("<label or id>")'
        )
    return "\n".join(lines)


def _check_plan_suggestion_from_data(session_id: str, data: dict | None) -> str | None:
    """Return a plan suggestion string if a fresh objective has no active plan.

    Accepts pre-fetched plan-context data. Returns None if no suggestion should
    be shown (no data, no objective, plan exists, objective is old, or already suggested).
    """
    if data is None:
        return None

    objective_id = (data.get("objective_id") or "").strip()
    objective_started_at = (data.get("objective_started_at") or "").strip()
    objective_title = (data.get("objective_title") or "").strip()
    saved_plan = data.get("saved_plan")

    # Only suggest when there's an active objective with no plan
    if not objective_id or saved_plan:
        return None

    # Only suggest for fresh objectives (< 10 min old)
    if objective_started_at:
        try:
            started = datetime.fromisoformat(objective_started_at.replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - started).total_seconds() / 60
            if age_min >= 10:
                return None
        except Exception:
            return None
    else:
        return None

    # Only suggest once per objective — track in a local cache file
    try:
        cache: dict = {}
        if _PLAN_SUGGESTION_CACHE.exists():
            try:
                cache = json.loads(_PLAN_SUGGESTION_CACHE.read_text())
            except Exception:
                cache = {}
        if objective_id in cache:
            return None
        # Mark as shown and persist (prune entries older than 24h)
        now_ts = time.time()
        cache[objective_id] = now_ts
        cache = {k: v for k, v in cache.items() if now_ts - v < 86400}
        _PLAN_SUGGESTION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _PLAN_SUGGESTION_CACHE.write_text(json.dumps(cache))
    except Exception:
        return None

    title_part = f' "{objective_title}"' if objective_title else ""
    return (
        f"[VibeCheck] New objective{title_part} detected — no active plan yet.\n"
        f"  Run /vibecheck:plan to structure your approach before diving in."
    )


def _check_workflow_nudge(
    api_url: str,
    auth_headers: dict,
    session_id: str,
    cwd: str,
    prompt: str,
    plan_context_data: dict | None,
) -> str | None:
    """Return a workflow nudge string if the user should be guided into the workflow.

    Only fires once per session. Requires an action-verb prompt. Uses the already-fetched
    plan-context data to avoid a second API call.

    Returns None if no nudge should be shown.
    """
    # Only nudge for action-intent prompts
    preprocessed = _preprocess_query(prompt)
    if not _TASK_INTENT_RE.match(preprocessed):
        return None

    # Check if already nudged this session
    if not session_id or session_id == "unknown":
        return None
    try:
        cache: dict = {}
        if _WORKFLOW_NUDGE_CACHE.exists():
            try:
                cache = json.loads(_WORKFLOW_NUDGE_CACHE.read_text())
            except Exception:
                cache = {}
        if session_id in cache:
            return None
    except Exception:
        return None

    if plan_context_data is None:
        return None

    active_spec_id = (plan_context_data.get("active_spec_id") or "").strip()
    saved_plan = plan_context_data.get("saved_plan")
    objective_started_at = (plan_context_data.get("objective_started_at") or "").strip()

    message: str | None = None

    # Case 1: No spec and no plan — suggest shape
    if not active_spec_id and not saved_plan:
        message = (
            "[VibeCheck] No spec or plan found for this session.\n"
            "  Run /vibecheck:shape to define what you're building before diving in."
        )

    # Case 2: Spec exists but no plan — suggest plan
    elif active_spec_id and not saved_plan:
        message = (
            f"[VibeCheck] Spec {active_spec_id} is active but no plan found.\n"
            "  Run /vibecheck:plan to structure your implementation steps."
        )

    # Case 3: Both spec and plan — suggest review if session is > 10 min old
    elif active_spec_id and saved_plan and objective_started_at:
        try:
            started = datetime.fromisoformat(objective_started_at.replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - started).total_seconds() / 60
            if age_min >= 10:
                message = (
                    "[VibeCheck] You have an active spec and plan.\n"
                    "  Run /vibecheck:review before committing to catch issues early."
                )
        except Exception:
            pass

    if message is None:
        return None

    # Mark session as nudged only after confirming there's something to say
    try:
        now_ts = time.time()
        cache[session_id] = now_ts
        cache = {k: v for k, v in cache.items() if now_ts - v < 86400}
        _WORKFLOW_NUDGE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _WORKFLOW_NUDGE_CACHE.write_text(json.dumps(cache))
    except Exception:
        pass

    return message


def _check_correction_signal(prompt: str) -> tuple[str, str] | None:
    """Return (matched_phrase, topic_context) if the prompt contains a convention correction.

    Pure regex — no I/O, no network calls.
    - matched_phrase: the pattern that fired (e.g. "I don't use")
    - topic_context: up to 60 chars following the match (contains the actual topic word)
    Returns None if no correction pattern is detected.
    """
    for pattern in _CORRECTION_PATTERNS:
        m = pattern.search(prompt)
        if m:
            topic_context = prompt[m.start():m.end() + 60]
            return (m.group(0), topic_context)
    return None


def _correction_already_covered(
    signal_phrase: str, topic_context: str, api_url: str, auth_headers: dict
) -> bool:
    """Return True if the correction topic is already covered by an always-inject standard.

    Fetches /api/contexts/standards once (only called when a signal is detected)
    and checks for keyword overlap between the topic context and existing standard
    titles/summaries. Returns False on any error so the nudge is not silently dropped.
    """
    try:
        url = f"{api_url}/api/contexts/standards"
        req = urllib_request.Request(
            url,
            headers={"Accept": "application/json", **auth_headers},
        )
        with urllib_request.urlopen(req, timeout=_PLAN_SUGGESTION_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Only check user/agent-created standards — not system-seeded review criteria
        # (e.g. "No Tokens Left in Code"). Built-in standards cover review concerns,
        # not user conventions, and their generic titles produce false dedup matches.
        standards = [
            s for s in data.get("standards", [])
            if s.get("always_inject") and s.get("created_by") != "system"
        ]
        if not standards:
            return False

        # Extract topic words from the broader context (signal phrase + following text).
        # Ignore common stop-words so we match on the actual subject (e.g. "bash", "zsh").
        _STOP = {
            "i", "we", "don't", "dont", "never", "always", "use", "run", "call",
            "do", "stop", "using", "not", "told", "you", "said", "this", "ve",
            "ive", "already", "a", "an", "the", "and", "or", "to", "for", "of",
            "in", "on", "at", "is", "it", "with", "that", "my", "our", "your",
        }
        topic_words = {
            w.lower()
            for w in re.findall(r"\w+", topic_context)
            if w.lower() not in _STOP and len(w) > 2
        }

        for std in standards:
            title_words = {w.lower() for w in re.findall(r"\w+", std.get("title", ""))}
            summary_words = {
                w.lower()
                for w in re.findall(r"\w+", std.get("context_summary", "") or "")
            }
            all_words = title_words | summary_words
            if topic_words and topic_words & all_words:
                return True
    except Exception:
        pass
    return False


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # UserPromptSubmit payload includes `prompt` — the user's raw message text.
    prompt = (hook_data.get("prompt") or "").strip()
    session_id = (hook_data.get("session_id") or "").strip()
    cwd = (hook_data.get("cwd") or "").strip()

    # Flush pending artifact capture echoes from PostToolUse hooks.
    try:
        if _PENDING_ECHOES.exists():
            echoes = _PENDING_ECHOES.read_text(encoding="utf-8").strip()
            if echoes:
                print(echoes)
                print()
            _PENDING_ECHOES.unlink(missing_ok=True)
    except Exception:
        pass

    if _should_skip(prompt):
        sys.exit(0)

    # Phase 3: preprocess the query to strip conversational filler.
    query = _preprocess_query(prompt)
    situation = prompt[:_QUERY_MAX_CHARS]

    try:
        auth_headers = resolve_auth_headers()
    except Exception:
        auth_headers = {}

    try:
        api_url = get_api_url()
    except Exception:
        sys.exit(0)

    # ── Plan context fetch (shared by plan suggestion + workflow nudge) ──
    # Fetch once and pass to both checks to avoid duplicate API calls.
    _plan_context_data: dict | None = None
    try:
        qs: dict = {}
        if cwd:
            qs["cwd"] = cwd
        if session_id and session_id != "unknown":
            qs["session_id"] = session_id
        if qs:
            _pc_url = f"{api_url}/api/plan-context?{urllib_parse.urlencode(qs)}"
            _pc_req = urllib_request.Request(_pc_url, headers={"Accept": "application/json", **auth_headers})
            with urllib_request.urlopen(_pc_req, timeout=_PLAN_SUGGESTION_TIMEOUT) as _pc_resp:
                _plan_context_data = json.loads(_pc_resp.read().decode("utf-8"))
    except Exception:
        pass

    # ── Plan suggestion (SPEC-177) ────────────────────────────────────────
    # Check once per fresh objective — never delays Claude's response.
    plan_suggestion: str | None = None
    try:
        plan_suggestion = _check_plan_suggestion_from_data(session_id, _plan_context_data)
    except Exception:
        pass

    # ── P2 workflow nudge (SPEC-198) ─────────────────────────────────────
    # One-time per-session nudge guiding user into the workflow.
    workflow_nudge: str | None = None
    if not plan_suggestion:  # Don't stack with plan suggestion
        try:
            workflow_nudge = _check_workflow_nudge(
                api_url, auth_headers, session_id, cwd, prompt, _plan_context_data
            )
        except Exception:
            pass

    # ── Correction signal detection (SPEC-322) ───────────────────────────
    # Detects convention corrections in the user's message (e.g. "I don't use bash")
    # and injects a nudge to capture the convention before it expires.
    correction_nudge: str | None = None
    try:
        _signal = _check_correction_signal(prompt)
        if _signal and not _correction_already_covered(_signal[0], _signal[1], api_url, auth_headers):
            correction_nudge = (
                "[VibeCheck] Correction signal detected. If this states a codebase convention,\n"
                "capture it before responding:\n"
                "  vibecheck_create_context(type=\"standard\", always_inject=True,\n"
                "    title=\"<convention in ~5 words>\",\n"
                "    brief=\"<when and how to apply it>\",\n"
                "    context_summary=\"<one sentence: when this rule applies>\")\n"
                "Then respond to the user normally."
            )
    except Exception:
        pass

    # ── Phase 5: Two-pass discovery ──────────────────────────────────────
    # Pass 1: Skills — "What should I do?"
    # Pass 2: General — "What should I know?" (excluding skills from pass 1)
    skills: list[dict] = []
    general: list[dict] = []

    try:
        skills = _discover(api_url, auth_headers, query, situation,
                           session_id, layer="skill", limit=_SKILL_LIMIT)
    except (HTTPError, URLError, OSError, Exception):
        pass

    try:
        general = _discover(api_url, auth_headers, query, situation,
                            session_id, layer=None, limit=_GENERAL_LIMIT + _SKILL_LIMIT)
    except (HTTPError, URLError, OSError, Exception):
        pass

    # Deduplicate: remove from general any contexts already in skills.
    skill_ids = {c.get("id") for c in skills}
    general = [c for c in general if c.get("id") not in skill_ids]

    # Also filter out skill-layer results from general pass (skills come from pass 1).
    general = [c for c in general if c.get("layer") != "skill"]
    general = general[:_GENERAL_LIMIT]

    contexts = skills + general
    if not contexts and not plan_suggestion and not workflow_nudge and not correction_nudge:
        sys.exit(0)

    if correction_nudge:
        print(correction_nudge)
        if contexts or plan_suggestion or workflow_nudge:
            print()
    if plan_suggestion:
        print(plan_suggestion)
        if contexts:
            print()
    if workflow_nudge:
        print(workflow_nudge)
        if contexts:
            print()
    if contexts:
        print(_format_brief(contexts))

    # Standing dedup instruction — always emit when any output was shown,
    # so Claude knows file-written artifacts are captured automatically.
    if contexts or plan_suggestion or workflow_nudge or correction_nudge:
        print(
            "\n[VibeCheck] File-written artifacts (specs, plans, design docs) are "
            "automatically captured. Only use vibecheck_create_context for decisions, "
            "findings, and insights from conversation — never for content just written to a file."
        )


if __name__ == "__main__":
    main()
