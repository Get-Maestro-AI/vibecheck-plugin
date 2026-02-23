"""Best-effort logging for plugin hook scripts.

Hook scripts must never fail Claude Code execution, so this logger:
- never raises
- logs to ~/.vibecheck/logs/plugin-hooks.log
- mirrors to stderr for immediate visibility when available
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import traceback
import sys


def log_hook_issue(script: str, message: str, exc: Exception | None = None) -> None:
    """Write a warning entry for hook failures/degraded behavior."""
    try:
        ts = datetime.now(timezone.utc).isoformat()
        logs_dir = Path.home() / ".vibecheck" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "plugin-hooks.log"
        line = f"{ts} [{script}] {message}"
        if exc:
            line += f" | {type(exc).__name__}: {exc}"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            if exc:
                f.write(traceback.format_exc() + "\n")
        try:
            print(line, file=sys.stderr)
        except Exception:
            pass
    except Exception:
        # Must never raise from logging path.
        return
