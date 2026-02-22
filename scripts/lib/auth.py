"""Credential resolution for plugin scripts.

Merges auth fields into outgoing event payloads.
Resolution order:
  1. VIBECHECK_API_KEY env var → {"api_key_hint": key[:8]}
  2. ~/.config/vibecheck/config.json api_key → same
  3. Claim token → {"claim_token": token}

Always returns a dict (never raises).
For local-only deployments the server accepts events without any auth.
"""
import json
import os
from pathlib import Path
from lib.claim import get_or_create_claim_token  # type: ignore[import]


def resolve_credentials() -> dict:
    """Return a dict of auth fields to merge into event payloads."""
    # Check env var first
    key = os.environ.get("VIBECHECK_API_KEY", "").strip()
    if key:
        return {"api_key_hint": key[:8]}

    # Check config file
    config_path = Path.home() / ".config" / "vibecheck" / "config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            key = data.get("api_key", "").strip()
            if key:
                return {"api_key_hint": key[:8]}
        except Exception:
            pass

    # Fall back to claim token (anonymous local use)
    return {"claim_token": get_or_create_claim_token()}
