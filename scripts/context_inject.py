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

Uses only stdlib. Always exits 0. Targets < 3s wall time.
"""
import json
import re
import sys
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


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # UserPromptSubmit payload includes `prompt` — the user's raw message text.
    prompt = (hook_data.get("prompt") or "").strip()
    session_id = (hook_data.get("session_id") or "").strip()

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
    if not contexts:
        sys.exit(0)

    print(_format_brief(contexts))


if __name__ == "__main__":
    main()
