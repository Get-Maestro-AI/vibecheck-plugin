"""Credential resolution for plugin scripts.

resolve_auth_headers() returns an HTTP headers dict with Authorization: Bearer <key>
when a plugin API key is configured.  Use this for all outgoing HTTP requests.

resolve_credentials() is kept for backward compatibility but is no longer used
by the main HTTP callers (push_event, push_turn, MCP server).

Resolution order for both functions:
  1. VIBECHECK_API_KEY env var
  2. ~/.config/vibecheck/config  (key=value, line: api_key=vc_...)
  3. Claim token fallback (anonymous local use, credentials only)

Always returns a dict (never raises).
For local-only deployments the server accepts events without any auth.
"""
import os
from pathlib import Path
from lib.claim import get_or_create_claim_token  # type: ignore[import]


def _resolve_api_key() -> str:
    """Return the configured API key string, or empty string if none."""
    key = os.environ.get("VIBECHECK_API_KEY", "").strip()
    if key:
        return key
    config_path = Path.home() / ".config" / "vibecheck" / "config"
    if config_path.exists():
        try:
            for line in config_path.read_text().splitlines():
                if line.startswith("api_key="):
                    key = line.split("=", 1)[1].strip()
                    if key:
                        return key
        except Exception:
            pass
    return ""


def resolve_auth_headers() -> dict:
    """Return HTTP headers dict for plugin requests.

    Returns {"Authorization": "Bearer <key>"} when a plugin API key is
    configured, otherwise an empty dict (anonymous local use).
    """
    key = _resolve_api_key()
    if key:
        return {"Authorization": f"Bearer {key}"}
    return {}


def get_auth_headers_for_index(n: int) -> dict:
    """Return auth headers for the nth configured target (1-indexed).

    n=1 uses the primary key (VIBECHECK_API_KEY / api_key).
    n>=2 checks VIBECHECK_API_KEY_N env then api_key_N config value.
    Returns {"Authorization": "Bearer <key>"} or {} if no key found.
    """
    if n == 1:
        key = _resolve_api_key()
    else:
        key = os.environ.get(f"VIBECHECK_API_KEY_{n}", "").strip()
        if not key:
            config_path = Path.home() / ".config" / "vibecheck" / "config"
            if config_path.exists():
                try:
                    for line in config_path.read_text().splitlines():
                        if line.startswith(f"api_key_{n}="):
                            key = line.split("=", 1)[1].strip()
                            if key:
                                break
                except Exception:
                    pass
    if key:
        return {"Authorization": f"Bearer {key}"}
    return {}


def resolve_credentials() -> dict:
    """Return a dict of auth fields to merge into event payloads (legacy).

    Kept for backward compatibility. Prefer resolve_auth_headers() for
    new HTTP request code.
    """
    key = _resolve_api_key()
    if key:
        return {"api_key_hint": key[:8]}
    return {"claim_token": get_or_create_claim_token()}
