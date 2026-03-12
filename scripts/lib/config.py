"""Plugin config: API endpoint and feature flags.

Resolution order for VIBECHECK_API_URL:
  1. VIBECHECK_API_URL environment variable
  2. ~/.config/vibecheck/config  (key=value, line: api_url=https://...)
  3. Default: http://localhost:8420
"""
import os
from pathlib import Path


def get_api_url() -> str:
    """Return the VibeCheck server URL."""
    env = os.environ.get("VIBECHECK_API_URL", "").strip()
    if env:
        return env.rstrip("/")

    config_path = Path.home() / ".config" / "vibecheck" / "config"
    if config_path.exists():
        try:
            for line in config_path.read_text().splitlines():
                if line.startswith("api_url="):
                    url = line.split("=", 1)[1].strip()
                    if url:
                        return url.rstrip("/")
        except Exception:
            pass

    return "http://localhost:8420"
