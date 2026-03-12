#!/usr/bin/env bash
# get-objective-files.sh
# Fetch the file list scoped to in-progress objectives from the VibeCheck dashboard.
# Prints one absolute or relative file path per line.
# Exits 0 in all cases — a non-responsive server is not an error.

set -euo pipefail

_VC_CONF="$HOME/.config/vibecheck/config"
VIBECHECK_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2- || true)}"
VIBECHECK_URL="${VIBECHECK_URL%/}"; VIBECHECK_URL="${VIBECHECK_URL:-http://localhost:8420}"
PROJECT_NAME="$(basename "$(pwd)")"

# Fetch the briefing with a 3-second timeout. If the server is unreachable, exit silently.
RESPONSE="$(curl -sf --max-time 3 "${VIBECHECK_URL}/api/projects/${PROJECT_NAME}/briefing" 2>/dev/null)" || {
  # Server unreachable or returned a non-2xx status — fall back gracefully.
  exit 0
}

# Parse: collect files_changed from objectives whose status is 'in_progress'.
echo "${RESPONSE}" | python3 - <<'PYEOF'
import sys, json

try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

objectives = data.get("objectives") or []
files: list[str] = []
for obj in objectives:
    if obj.get("status") == "in_progress":
        files.extend(obj.get("files_changed") or [])

# Deduplicate while preserving order.
seen: set[str] = set()
for f in files:
    if f and f not in seen:
        print(f)
        seen.add(f)
PYEOF
