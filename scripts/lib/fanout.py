"""Fan-out HTTP POST to all configured VibeCheck targets.

post_to_targets(path, payload, timeout=5) -> dict
  - POSTs to every URL from get_api_targets() in order (best-effort)
  - Returns the primary target's response dict, or {"ok": True} if it fails
  - Secondary target failures are logged but never propagated

Uses only stdlib (urllib). Always returns a dict; never raises.
"""
import json
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from lib.config import get_api_targets  # type: ignore[import]
from lib.auth import get_auth_headers_for_index  # type: ignore[import]
from lib.hook_log import log_hook_issue  # type: ignore[import]


def post_to_targets(path: str, payload: dict, timeout: int = 5) -> dict:
    """POST payload to all configured API targets. Returns primary response."""
    targets = get_api_targets()
    data = json.dumps(payload, default=str).encode()
    primary_response: dict = {"error": "primary target unreachable"}

    for n, target_url in enumerate(targets, start=1):
        auth_headers: dict = {}
        try:
            auth_headers = get_auth_headers_for_index(n)
        except Exception:
            pass

        try:
            req = urllib_request.Request(
                f"{target_url}{path}",
                data=data,
                headers={"Content-Type": "application/json", **auth_headers},
                method="POST",
            )
            with urllib_request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                response = json.loads(body) if body else {"ok": True}
                if n == 1:
                    primary_response = response
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:800]
            except Exception:
                pass
            label = "Primary" if n == 1 else f"Secondary target {n}"
            log_hook_issue(
                "fanout",
                f"{label} {path} failed (status={e.code}, response={body})",
                e,
            )
        except (URLError, OSError, Exception) as e:
            label = "Primary" if n == 1 else f"Secondary target {n}"
            log_hook_issue("fanout", f"{label} {path} failed", e)

    return primary_response
