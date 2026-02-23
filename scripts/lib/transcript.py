"""Lightweight JSONL transcript parser (stdlib only).

Extracts the minimal data the server needs for objective clustering and
alignment checks. Written defensively — every field access is wrapped in
try/except. Unknown JSONL entry types are skipped. A parse failure at
any point returns whatever data was collected up to that point.

NOT a full reconstruction of ClaudeCodeAdapter.get_session() — this is
a thin extraction layer for session_summary.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# How many lines to read at a time (streaming)
CHUNK_LINES = 500
# Max turns to include in the conversation window
WINDOW_SIZE = 15
# Max file size to parse fully; larger files use tail
MAX_FULL_PARSE_BYTES = 2 * 1024 * 1024  # 2MB


def parse_transcript(path: str) -> dict:
    """Parse a Claude Code JSONL transcript and return a SessionSummaryPayload dict.

    Returns a dict matching the SessionSummaryPayload model structure.
    Never raises — returns partial data on any error.
    """
    result: dict[str, Any] = {
        "first_prompt": "",
        "final_prompt": "",
        "total_turns": 0,
        "tool_call_counts": {},
        "token_usage": {},
        "model": "",
        "objectives_raw": [],
        "conversation_window": [],
        "files_modified": [],
        "error_count": 0,
        "consecutive_errors": 0,
        "user_entries_total": 0,
        "user_prompt_entries": 0,
        "user_tool_result_entries": 0,
        "parse_degraded": False,
        "parse_degraded_reason": "",
    }

    try:
        p = Path(path)
        if not p.exists():
            return result

        # All entries for building the window and objectives
        all_turns: list[dict] = []
        tool_counts: dict[str, int] = {}
        token_input = 0
        token_output = 0
        token_cache_read = 0
        token_cache_create = 0
        model = ""
        files_modified: set[str] = set()
        error_count = 0
        consecutive = 0
        max_consecutive = 0

        file_size = p.stat().st_size
        if file_size > MAX_FULL_PARSE_BYTES:
            # For very large files, only read the tail for the window
            # but stream the full file for counts
            pass  # Will stream below regardless

        with open(p, encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")

                # Human turn
                if _is_user_entry(entry_type):
                    try:
                        result["user_entries_total"] += 1
                        msg = entry.get("message", {})
                        content = msg.get("content", [])
                        text = _extract_text(content)
                        has_tool_result = _has_tool_result_block(content)
                        if has_tool_result:
                            result["user_tool_result_entries"] += 1
                        if text:
                            result["user_prompt_entries"] += 1
                            if not result["first_prompt"]:
                                result["first_prompt"] = text[:2000]
                            result["final_prompt"] = text[:2000]
                            all_turns.append({"role": "human", "text": text[:1000]})
                            result["total_turns"] += 1
                    except Exception:
                        pass

                # Assistant turn
                elif entry_type == "assistant":
                    try:
                        msg = entry.get("message", {})
                        content = msg.get("content", [])
                        text = _extract_text(content)

                        # Token usage
                        usage = msg.get("usage", {})
                        if usage:
                            token_input += usage.get("input_tokens", 0)
                            token_output += usage.get("output_tokens", 0)
                            token_cache_read += usage.get("cache_read_input_tokens", 0)
                            token_cache_create += usage.get("cache_creation_input_tokens", 0)

                        # Model
                        if not model and msg.get("model"):
                            model = msg["model"]

                        if text:
                            all_turns.append({"role": "assistant", "text": text[:1000]})

                        # Tool use blocks
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_use":
                                    tool_name = block.get("name", "unknown")
                                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                                    # Track modified files
                                    inp = block.get("input", {})
                                    if tool_name in ("Write", "Edit", "MultiEdit"):
                                        fp = inp.get("file_path") or inp.get("path", "")
                                        if fp:
                                            files_modified.add(fp)
                    except Exception:
                        pass

                # Tool result (for error tracking)
                elif entry_type == "tool_result":
                    try:
                        exit_code = entry.get("exit_code")
                        if exit_code and int(exit_code) != 0:
                            error_count += 1
                            consecutive += 1
                            max_consecutive = max(max_consecutive, consecutive)
                        else:
                            consecutive = 0
                    except Exception:
                        pass

    except Exception:
        pass  # Return whatever we have

    # Build results
    result["tool_call_counts"] = tool_counts
    result["token_usage"] = {
        "input_tokens": token_input,
        "output_tokens": token_output,
        "cache_read_tokens": token_cache_read,
        "cache_creation_tokens": token_cache_create,
    }
    result["model"] = model
    result["files_modified"] = list(files_modified)[:50]
    result["error_count"] = error_count
    result["consecutive_errors"] = max_consecutive
    if all_turns and result["total_turns"] == 0:
        has_assistant = any(t.get("role") == "assistant" for t in all_turns)
        if has_assistant:
            result["parse_degraded"] = True
            result["parse_degraded_reason"] = "assistant_seen_without_user_turns"

    # Conversation window (last N turns for LLM context)
    result["conversation_window"] = [
        {"role": t["role"], "text": t["text"]}
        for t in all_turns[-WINDOW_SIZE:]
    ]

    # Objectives raw: all human turns (for ObjectiveClusterer)
    result["objectives_raw"] = [
        {"role": t["role"], "text": t["text"], "turn_index": i}
        for i, t in enumerate(all_turns)
        if t["role"] == "human" and t["text"]
    ]

    return result


def _extract_text(content: Any) -> str:
    """Extract plain text from a message content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(p for p in parts if p)
    return ""


def _is_user_entry(entry_type: str) -> bool:
    return entry_type in {"human", "user"}


def _has_tool_result_block(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            return True
    return False
