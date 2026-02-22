"""Claim token: anonymous session identifier for local-only use.

Generated once and persisted to ~/.config/vibecheck/session.json.
Allows the server to associate events from the same developer across sessions
without requiring an API key.
"""
import json
import os
import uuid
from pathlib import Path

CLAIM_TOKEN_PATH = Path.home() / ".config" / "vibecheck" / "session.json"


def get_or_create_claim_token() -> str:
    """Return the persistent claim token, creating it if it doesn't exist."""
    try:
        if CLAIM_TOKEN_PATH.exists():
            data = json.loads(CLAIM_TOKEN_PATH.read_text())
            token = data.get("claim_token", "")
            if token:
                return token
    except Exception:
        pass

    token = str(uuid.uuid4())
    try:
        CLAIM_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        CLAIM_TOKEN_PATH.write_text(json.dumps({"claim_token": token}))
    except Exception:
        pass  # Can't persist — use ephemeral token
    return token
