---
description: Resolve a context (issue, spec, etc.) from the VibeCheck dashboard
allowed-tools: Bash
---

Resolve the specified context(s) in the VibeCheck dashboard.

Context IDs to resolve (space-separated): $ARGUMENTS

Accepts either the UUID returned by `/vibecheck:review` or the ISS-XX label shown on the dashboard.
Use the ID exactly as returned — do not guess.

For each ID in the arguments, run the following curl command (substituting the actual ID):

```bash
_VC_CONF="$HOME/.config/vibecheck/config.json"
_VC_KEY="${VIBECHECK_API_KEY:-$(sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"
_VC_URL="${VIBECHECK_API_URL:-$(sed -n 's/.*"api_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"
_VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"
_AUTH_ARGS=()
[ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY")

curl -s -X POST "$_VC_URL/api/push/dismiss-issue" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d "{\"session_id\": \"${CLAUDE_SESSION_ID:-unknown}\", \"cwd\": \"$(pwd)\", \"issue_id\": \"<ID>\"}"
```

After running each curl, report to the user:
- Which contexts were resolved (server returned `{"dismissed": 1}`)
- Which were not found (server returned `{"dismissed": 0}`)
- Any errors (server unreachable, non-200 response)

If no arguments are provided, explain usage:
  `/vibecheck:resolve ISS-33` — resolve by ISS-XX label
  `/vibecheck:resolve 3f8a1b2c-...` — resolve by UUID
  `/vibecheck:resolve ISS-33 ISS-34` — resolve multiple at once
