#!/usr/bin/env python3
"""Per-turn lightweight transcript tail-read.

Runs on every Stop event (async, 10s timeout).
Reads only the last 32KB of the transcript JSONL file (O(1) regardless of
session length), extracts the latest user/assistant turn pair, and POSTs a
TurnPayload to the server alongside the Stop hook event.

Also does a fast forward-scan of the full transcript to accumulate cumulative
token counts (input/output/cache) for mid-session cost visibility. This scan
skips all content fields — only parses message.usage from assistant entries.

Uses only stdlib. Always exits 0.
"""
import json
import os
import sys
import hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from lib.fanout import post_to_targets  # type: ignore[import]
from lib.hook_log import log_hook_issue  # type: ignore[import]

# Bounded tail-read: last 32KB is sufficient for any recent turn pair
TAIL_BYTES = 32 * 1024


def _is_user_entry(entry_type: str) -> bool:
    return entry_type in {"human", "user"}


def _extract_user_text(entry: dict) -> str:
    msg = entry.get("message", {})
    content = msg.get("content", [])
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return " ".join(texts).strip()[:2000]
    if isinstance(content, str):
        return content.strip()[:2000]
    return ""


def _build_event_id(hook_data: dict) -> str:
    stable = {
        k: v for k, v in hook_data.items()
        if k not in {"event_id", "event_seq", "event_source", "plugin_version"}
    }
    blob = json.dumps(stable, sort_keys=True, default=str)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()[:16]


def extract_latest_turn(transcript_path: str) -> dict:
    """Read the tail of a JSONL transcript and extract the latest turn pair.

    Returns:
        {
          "user_prompt": str,
          "assistant_response": str,
          "turn_index": int,
          "task_create_order": list[{"subject": str}],  # TaskCreate calls in response order
        }
    Returns empty strings / empty list on any failure.
    """
    try:
        path = Path(transcript_path)
        if not path.exists():
            return {"user_prompt": "", "assistant_response": "", "turn_index": 0,
                    "task_create_order": []}

        file_size = path.stat().st_size
        seek_pos = max(0, file_size - TAIL_BYTES)

        with open(path, "rb") as f:
            f.seek(seek_pos)
            if seek_pos > 0:
                # Skip the (possibly partial) first line after seeking
                f.readline()
            tail_bytes = f.read()

        lines = tail_bytes.decode("utf-8", errors="replace").splitlines()

        # Parse JSONL entries from the tail
        entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue

        # Find the latest user prompt and assistant response
        user_prompt = ""
        assistant_response = ""
        task_create_order = []
        turn_index = 0
        parse_degraded = False
        parse_degraded_reason = ""

        # Walk backwards to find the most recent assistant turn, then user turn before it
        for i in range(len(entries) - 1, -1, -1):
            entry = entries[i]
            entry_type = entry.get("type", "")

            # Assistant message: extract text content and TaskCreate tool_use order
            if not assistant_response and entry_type == "assistant":
                msg = entry.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    texts = []
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        block_type = block.get("type", "")
                        if block_type == "text":
                            texts.append(block.get("text", ""))
                        elif block_type == "tool_use":
                            name = block.get("name", "")
                            inp = block.get("input", {})
                            if name == "TaskCreate":
                                subject = (inp.get("subject") or "").strip()
                                if subject:
                                    task_create_order.append({"subject": subject})
                                    texts.append(f"`TaskCreate: {subject[:120]}`")
                            elif name == "Bash":
                                cmd = (inp.get("command") or "").strip()
                                desc = (inp.get("description") or "").strip()
                                header = f"*{desc}*\n" if desc else ""
                                texts.append(f"\n{header}```bash\n{cmd[:800]}\n```")
                            elif name in ("Edit", "Write", "NotebookEdit"):
                                fp = (inp.get("file_path") or inp.get("notebook_path") or "").strip()
                                texts.append(f"`{name}: {fp}`")
                            elif name == "Read":
                                fp = (inp.get("file_path") or "").strip()
                                texts.append(f"`Read: {fp}`")
                            elif name == "Grep":
                                pattern = (inp.get("pattern") or "").strip()
                                path = (inp.get("path") or "").strip()
                                loc = f" in {path}" if path else ""
                                texts.append(f"`Grep: \"{pattern[:60]}\"{loc}`")
                            elif name == "Glob":
                                pattern = (inp.get("pattern") or "").strip()
                                texts.append(f"`Glob: {pattern}`")
                            elif name == "Task":
                                desc = (inp.get("description") or inp.get("prompt") or "").strip()
                                texts.append(f"`Task (agent): {desc[:120]}`")
                            elif name == "TaskUpdate":
                                tid = inp.get("taskId", "")
                                status = inp.get("status", "")
                                if status:
                                    texts.append(f"`TaskUpdate #{tid} → {status}`")
                            elif name == "AskUserQuestion":
                                questions = inp.get("questions") or []
                                if questions:
                                    q = (questions[0].get("question") or "").strip()
                                    texts.append(f"`AskUser: {q[:120]}`")
                            elif name == "ExitPlanMode":
                                texts.append("`ExitPlanMode: awaiting plan approval`")
                            elif name == "EnterPlanMode":
                                texts.append("`EnterPlanMode`")
                            elif name == "WebFetch":
                                url = (inp.get("url") or "").strip()
                                texts.append(f"`WebFetch: {url[:120]}`")
                            elif name == "WebSearch":
                                query = (inp.get("query") or "").strip()
                                texts.append(f"`WebSearch: {query[:120]}`")
                            elif name.startswith("mcp__"):
                                short = name.split("__")[-1]
                                status_label = inp.get("status_label", "")
                                label = f" [{status_label}]" if status_label else ""
                                texts.append(f"`mcp:{short}{label}`")
                    assistant_response = "\n\n".join(texts).strip()[:12000]  # increased from 4000
                elif isinstance(content, str):
                    assistant_response = content[:12000]  # increased from 4000
                continue

            # User message: extract prompt text
            if assistant_response and not user_prompt and _is_user_entry(entry_type):
                user_prompt = _extract_user_text(entry)
                if user_prompt:
                    break

        # Approximate turn index from entry count
        turn_index = max(
            0,
            len(
                [
                    e for e in entries
                    if _is_user_entry(e.get("type", "")) and _extract_user_text(e)
                ]
            ),
        )
        if not user_prompt:
            parse_degraded = True
            parse_degraded_reason = "assistant_seen_without_user_pair"
            # Fallback: scan the full transcript to recover user_prompt/turn_index.
            # Runs whenever user_prompt is missing — covers both the normal "assistant
            # present but user fell outside 32KB tail" case and the case where the
            # tail only contained unhandled tool_use blocks (e.g. ExitPlanMode on a
            # large transcript), leaving assistant_response empty as well.
            recovered_prompt, recovered_turn_index = _recover_user_context_full_scan(path)
            if recovered_turn_index > turn_index:
                turn_index = recovered_turn_index
            if recovered_prompt:
                user_prompt = recovered_prompt
                parse_degraded = False
                parse_degraded_reason = ""

        return {
            "user_prompt": user_prompt,
            "assistant_response": assistant_response,
            "turn_index": turn_index,
            "task_create_order": task_create_order,
            "parse_degraded": parse_degraded,
            "parse_degraded_reason": parse_degraded_reason,
        }

    except Exception as e:
        log_hook_issue("push_turn", "Failed while extracting latest turn", e)
        return {
            "user_prompt": "",
            "assistant_response": "",
            "turn_index": 0,
            "task_create_order": [],
            "parse_degraded": True,
            "parse_degraded_reason": "extract_exception",
        }


def extract_token_cumulative(transcript_path: str) -> dict | None:
    """Forward-scan the transcript summing token usage from all assistant entries.

    Skips all content — only reads message.usage dicts. O(n) in file size but
    fast because there is no string allocation or content processing.
    Returns None on any failure so callers can safely omit it.
    """
    try:
        token_input = 0
        token_output = 0
        cache_read = 0
        cache_create = 0
        model = ""
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                msg = entry.get("message", {})
                usage = msg.get("usage", {})
                if usage:
                    token_input  += usage.get("input_tokens", 0)
                    token_output += usage.get("output_tokens", 0)
                    cache_read   += usage.get("cache_read_input_tokens", 0)
                    cache_create += usage.get("cache_creation_input_tokens", 0)
                if not model and msg.get("model"):
                    model = msg["model"]
        return {
            "input_tokens": token_input,
            "output_tokens": token_output,
            "cache_read_tokens": cache_read,
            "cache_creation_tokens": cache_create,
            "model": model,
        }
    except Exception as e:
        log_hook_issue("push_turn", "Failed while scanning token totals", e)
        return None


def _recover_user_context_full_scan(path: Path) -> tuple[str, int]:
    """Recover user prompt and accurate turn count via full transcript scan."""
    user_count = 0
    last_user = ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not _is_user_entry(entry.get("type", "")):
                    continue
                text = _extract_user_text(entry)
                if text:
                    last_user = text
                    user_count += 1
    except Exception:
        return "", 0
    return last_user, user_count


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception as e:
        log_hook_issue("push_turn", "Failed to parse hook payload JSON", e)
        sys.exit(0)

    transcript_path = hook_data.get("transcript_path", "")
    turn_payload: dict | None = None

    if transcript_path and os.path.exists(transcript_path):
        turn_payload = extract_latest_turn(transcript_path)

    if not turn_payload or (not turn_payload.get("user_prompt") and not turn_payload.get("assistant_response")):
        # Nothing useful to push
        log_hook_issue("push_turn", "Turn payload empty; skipping push")
        sys.exit(0)

    # Accumulate cumulative token counts for mid-session cost visibility.
    # Runs on the same file already opened above; None on any failure.
    token_cumulative = None
    if transcript_path and os.path.exists(transcript_path):
        token_cumulative = extract_token_cumulative(transcript_path)

    turn_payload["token_cumulative"] = token_cumulative

    payload = {
        **hook_data,
        "event_id": _build_event_id(hook_data),
        "event_source": "push_turn",
        "turn_payload": turn_payload,
        "plugin_version": "1.0.0",
    }

    post_to_targets("/api/push/hook-event", payload)


if __name__ == "__main__":
    main()
