---
description: Flag a problem so it appears in the VibeCheck dashboard
allowed-tools: Bash
---

Create a user-reported issue in the VibeCheck dashboard for the current project.

**Issue description:** $ARGUMENTS

## Steps

1. Capture the current code context:

```bash
git diff --cached 2>/dev/null | head -200
git diff 2>/dev/null | head -200
```

2. Build and submit the payload to VibeCheck:

```bash
_VC_CONF="$HOME/.config/vibecheck/config.json"
_VC_KEY="${VIBECHECK_API_KEY:-$(sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"
_VC_URL="${VIBECHECK_API_URL:-$(sed -n 's/.*"api_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"
_VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"
_AUTH_ARGS=()
[ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY")

curl -s -X POST "$_VC_URL/api/push/create-issue" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d '{
    "session_id": "'"${CLAUDE_SESSION_ID:-unknown}"'",
    "cwd": "'"$(pwd)"'",
    "description": "<DESCRIPTION FROM $ARGUMENTS>",
    "diff_context": "<PASTE TRUNCATED DIFF HERE>",
    "severity": "warning"
  }'
```

Replace `<DESCRIPTION FROM $ARGUMENTS>` with the verbatim issue description provided by the user and `<PASTE TRUNCATED DIFF HERE>` with the diff output captured above (truncate to ~2000 chars if large).

3. Report back to the user:
   - Confirm the issue was created and show the LLM-generated title
   - Show the issue's assigned ID in `PREFIX-N` format (e.g. `VC-405`) — this is what you'll pass to `/vibecheck:fix` or `/vibecheck:dismiss-issue`
   - If VibeCheck is not running (`curl` fails or connection refused), tell the user — the issue was not saved
   - If the response includes `"llm_enriched": false`, note that summaries are disabled (no API key) so the raw description was used as-is

## Notes

- The backend calls Sonnet to generate a polished title, description, and suggested action from the raw description + diff context
- The issue appears in the VibeCheck dashboard under the current project with category "Reported"
- Every issue is assigned a project-prefixed ID in `PREFIX-N` format (e.g. `VC-401`), where `PREFIX` is derived from the project name initials and `N` is the alert's database ID
- Use `/vibecheck:dismiss-issue VC-401` to remove the alert once the underlying problem is resolved
- Use `/vibecheck:review` for a full pre-commit gate check across all staged changes
