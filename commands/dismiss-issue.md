---
description: Clear one or more resolved issues from the dashboard
allowed-tools: Bash
---

Dismiss the specified blocking issue(s) from the VibeCheck dashboard.

Issue IDs to dismiss (space-separated): $ARGUMENTS

For each issue ID in the arguments, run the following curl command (substituting the actual ID):

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
- Which issues were dismissed (server returned `{"ok": true}`)
- Which issues were not found (server returned `{"ok": true, "dismissed": 0}`)
- Any errors (server unreachable, non-200 response)

If no arguments are provided, explain usage:
  `/vibecheck:dismiss-issue VC-401` — dismiss a single issue
  `/vibecheck:dismiss-issue VC-401 VC-402 VC-403` — dismiss multiple issues at once

Issue IDs must use the full project-prefixed format shown on the issue card (e.g. "VC-401"), not a bare number.
