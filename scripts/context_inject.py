#!/usr/bin/env python3
"""Context injection hook for UserPromptSubmit.

Runs SYNCHRONOUSLY on every UserPromptSubmit — stdout is visible to Claude
before it processes the user's message.

Queries the VibeCheck Context Library using the user's prompt and prints
the top relevant contexts as a structured brief. This closes the ambient
injection gap: context flows into sessions automatically without Claude
needing to manually call vibecheck_discover.

Uses only stdlib. Always exits 0. Targets < 2.5s wall time.
"""
import json
import sys
from pathlib import Path
from urllib import request as urllib_request
from urllib import parse as urllib_parse
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import resolve_auth_headers  # type: ignore[import]
from lib.config import get_api_url          # type: ignore[import]

# Prompts shorter than this are likely one-word replies or continuations.
_MIN_PROMPT_LEN = 25

# Prompt prefixes that indicate a short continuation — skip injection for these.
_SKIP_PREFIXES = (
    "yes", "no", "ok", "okay", "sure", "thanks", "thank you",
    "got it", "sounds good", "looks good", "good", "great", "perfect",
    "continue", "go ahead", "do it", "proceed", "keep going",
    "agreed", "correct", "right", "exactly", "yep", "nope",
)

# Max characters of the prompt to use as the search query.
_QUERY_MAX_CHARS = 400

# HTTP timeout — tight to avoid blocking Claude's response.
_HTTP_TIMEOUT = 2.5

# Max contexts to surface.
_MAX_RESULTS = 4


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


def _format_brief(contexts: list[dict]) -> str:
    """Format discovered contexts as a concise brief Claude will act on."""
    lines = ["[VibeCheck] Relevant context for this task:\n"]
    for c in contexts:
        label = c.get("label", "")
        title = c.get("title", "")
        layer = c.get("layer", "")

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

    query = prompt[:_QUERY_MAX_CHARS]

    try:
        auth_headers = resolve_auth_headers()
    except Exception:
        auth_headers = {}

    try:
        api_url = get_api_url()

        qs: dict = {"q": query, "situation": query, "limit": _MAX_RESULTS}
        if session_id and session_id != "unknown":
            qs["session_id"] = session_id

        url = f"{api_url}/api/contexts/discover?{urllib_parse.urlencode(qs)}"
        req = urllib_request.Request(url, headers={"Accept": "application/json", **auth_headers})

        with urllib_request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

    except (HTTPError, URLError, OSError, Exception):
        # Server unavailable or slow — fail silently, never block Claude.
        sys.exit(0)

    contexts = data.get("contexts", [])
    if not contexts:
        sys.exit(0)

    print(_format_brief(contexts))


if __name__ == "__main__":
    main()
