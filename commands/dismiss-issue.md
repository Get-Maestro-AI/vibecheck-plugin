---
description: Clear one or more resolved issues from the dashboard
allowed-tools: Bash
---

Dismiss the specified blocking issue(s) from the VibeCheck dashboard.

Issue IDs to dismiss (space-separated): $ARGUMENTS

For each issue ID in the arguments, run the following curl command (substituting the actual ID):

```bash
curl -s -X POST http://localhost:8420/api/push/dismiss-issue \
  -H "Content-Type: application/json" \
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
