"""Plugin config: API endpoint and feature flags.

Resolution order for VIBECHECK_API_URL:
  1. VIBECHECK_API_URL environment variable
  2. ~/.config/vibecheck/config.json  {"api_url": "..."}
  3. Default: http://localhost:8420
"""
import json
import os
from pathlib import Path


def get_api_url() -> str:
    """Return the VibeCheck server URL."""
    env = os.environ.get("VIBECHECK_API_URL", "").strip()
    if env:
        return env.rstrip("/")

    config_path = Path.home() / ".config" / "vibecheck" / "config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            url = data.get("api_url", "").strip()
            if url:
                return url.rstrip("/")
        except Exception:
            pass

    return "http://localhost:8420"
