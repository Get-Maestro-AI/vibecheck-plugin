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
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent))

from lib.auth import resolve_credentials  # type: ignore[import]
from lib.config import get_api_url  # type: ignore[import]

# Bounded tail-read: last 32KB is sufficient for any recent turn pair
TAIL_BYTES = 32 * 1024


def extract_latest_turn(transcript_path: str) -> dict:
    """Read the tail of a JSONL transcript and extract the latest turn pair.

    Returns {"user_prompt": str, "assistant_response": str, "turn_index": int}.
    Returns empty strings on any failure.
    """
    try:
        path = Path(transcript_path)
        if not path.exists():
            return {"user_prompt": "", "assistant_response": "", "turn_index": 0}

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
        turn_index = 0

        # Walk backwards to find the most recent assistant turn, then user turn before it
        for i in range(len(entries) - 1, -1, -1):
            entry = entries[i]
            entry_type = entry.get("type", "")

            # Assistant message: extract text content
            if not assistant_response and entry_type == "assistant":
                msg = entry.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    texts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block.get("text", ""))
                    assistant_response = " ".join(texts)[:4000]
                elif isinstance(content, str):
                    assistant_response = content[:4000]
                continue

            # User message: extract prompt text
            if assistant_response and not user_prompt and entry_type == "human":
                msg = entry.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    texts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block.get("text", ""))
                    user_prompt = " ".join(texts)[:2000]
                elif isinstance(content, str):
                    user_prompt = content[:2000]
                break

        # Approximate turn index from entry count
        turn_index = max(0, len([e for e in entries if e.get("type") == "human"]))

        return {
            "user_prompt": user_prompt,
            "assistant_response": assistant_response,
            "turn_index": turn_index,
        }

    except Exception:
        return {"user_prompt": "", "assistant_response": "", "turn_index": 0}


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
    except Exception:
        return None


def main() -> None:
    try:
        hook_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    transcript_path = hook_data.get("transcript_path", "")
    turn_payload: dict | None = None

    if transcript_path and os.path.exists(transcript_path):
        turn_payload = extract_latest_turn(transcript_path)

    if not turn_payload or (not turn_payload.get("user_prompt") and not turn_payload.get("assistant_response")):
        # Nothing useful to push
        sys.exit(0)

    # Accumulate cumulative token counts for mid-session cost visibility.
    # Runs on the same file already opened above; None on any failure.
    token_cumulative = None
    if transcript_path and os.path.exists(transcript_path):
        token_cumulative = extract_token_cumulative(transcript_path)

    turn_payload["token_cumulative"] = token_cumulative

    creds = {}
    try:
        creds = resolve_credentials()
    except Exception:
        pass

    payload = {
        **hook_data,
        **creds,
        "turn_payload": turn_payload,
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
        with urllib_request.urlopen(req, timeout=5):
            pass
    except (URLError, OSError, Exception):
        pass


if __name__ == "__main__":
    main()
