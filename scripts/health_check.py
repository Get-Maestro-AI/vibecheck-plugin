#!/usr/bin/env python3
"""Session-start health check.

Verifies connectivity to the VibeCheck server and initializes the claim token.
Runs on SessionStart (async, 5s timeout).
Outputs a single status line to stderr — never blocks Claude Code.
Always exits 0.
"""
import json
import sys
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent))

from lib.config import get_api_url  # type: ignore[import]
from lib.claim import get_or_create_claim_token  # type: ignore[import]


def main() -> None:
    # Ensure claim token exists (idempotent)
    try:
        get_or_create_claim_token()
    except Exception:
        pass

    api_url = get_api_url()
    try:
        req = urllib_request.Request(f"{api_url}/api/health", headers={"User-Agent": "vibecheck-plugin/2.0"}, method="GET")
        with urllib_request.urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read())
            if body.get("ok"):
                print(f"[vibecheck] Connected to {api_url}", file=sys.stderr)
            else:
                print(f"[vibecheck] Server at {api_url} returned unexpected response", file=sys.stderr)
                sys.exit(1)
    except (URLError, OSError):
        print(f"[vibecheck] Server not reachable at {api_url} — run: python -m vibecheck", file=sys.stderr)
        sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
