"""Plugin config: API endpoint and feature flags.

Resolution order for VIBECHECK_API_URL:
  1. VIBECHECK_API_URL environment variable
  2. ~/.config/vibecheck/config  (key=value, line: api_url=https://...)
  3. Default: http://localhost:8420

Resolution order for VIBECHECK_FRONTEND_URL:
  1. VIBECHECK_FRONTEND_URL environment variable
  2. ~/.config/vibecheck/config  (key=value, line: frontend_url=https://...)
  3. Default: http://localhost:5173
"""
import os
from pathlib import Path


def _read_config_value(key: str) -> str | None:
    config_path = Path.home() / ".config" / "vibecheck" / "config"
    if config_path.exists():
        try:
            for line in config_path.read_text().splitlines():
                if line.startswith(f"{key}="):
                    val = line.split("=", 1)[1].strip()
                    if val:
                        return val
        except Exception:
            pass
    return None


def get_api_url() -> str:
    """Return the VibeCheck server URL."""
    env = os.environ.get("VIBECHECK_API_URL", "").strip()
    if env:
        return env.rstrip("/")
    val = _read_config_value("api_url")
    if val:
        return val.rstrip("/")
    return "http://localhost:8420"


def get_frontend_url() -> str:
    """Return the VibeCheck frontend URL."""
    env = os.environ.get("VIBECHECK_FRONTEND_URL", "").strip()
    if env:
        return env.rstrip("/")
    val = _read_config_value("frontend_url")
    if val:
        return val.rstrip("/")
    return "http://localhost:5173"
