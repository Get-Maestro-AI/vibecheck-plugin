---
description: Flag a code issue in the VibeCheck dashboard. The backend enriches the description with an LLM-generated title and action.
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
curl -s -X POST http://localhost:8420/api/push/create-issue \
  -H "Content-Type: application/json" \
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
   - If VibeCheck is not running (`curl` fails or connection refused), tell the user — the issue was not saved
   - If the response includes `"llm_enriched": false`, note that summaries are disabled (no API key) so the raw description was used as-is

## Notes

- The backend calls Sonnet to generate a polished title, description, and suggested action from the raw description + diff context
- The issue appears in the VibeCheck dashboard under the current project with category "Reported"
- Use `/vibecheck:dismiss-issue` to remove the alert once the underlying problem is resolved
- Use `/vibecheck:review` for a full pre-commit gate check across all staged changes
