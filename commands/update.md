---
description: Post a progress checkpoint to the VibeCheck dashboard
allowed-tools: Bash
---

Submit a `vibecheck_update` status checkpoint for the current project.

Arguments:
- `$ARGUMENTS` must be JSON with:
  - required: `status_label`, `summary`
  - optional: `current_task`, `completed_subtasks`, `files_modified`, `confidence`, `next_step`

Example:
`/vibecheck:update {"status_label":"implementing","summary":"Implemented completion protocol hardening.","current_task":"Cleaning objective resolution fallbacks","completed_subtasks":["Added robust fallback rules"],"files_modified":["vibecheck/event_processor.py"]}`

## Steps

1. Validate arguments:
   - If `$ARGUMENTS` is empty, explain usage and show the example above.
   - If JSON parsing fails, report "Invalid JSON" and show the expected shape.
   - If `status_label` or `summary` is missing, stop and report the missing field.

2. Submit update to VibeCheck:

```bash
PAYLOAD=$(python3 - <<'PY'
import json
import os
import sys
import uuid

raw = """$ARGUMENTS""".strip()
if not raw:
    print("ERROR: missing arguments")
    sys.exit(2)

try:
    data = json.loads(raw)
except Exception:
    print("ERROR: invalid JSON")
    sys.exit(2)

status = (data.get("status_label") or "").strip()
summary = (data.get("summary") or "").strip()
if not status:
    print("ERROR: missing status_label")
    sys.exit(2)
if not summary:
    print("ERROR: missing summary")
    sys.exit(2)

payload = {
    "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
    "cwd": os.getcwd(),
    "event_uuid": str(uuid.uuid4()),
    "report_type": "checkpoint",
    "status_label": status,
    "summary": summary,
    "current_task": data.get("current_task", ""),
    "completed_subtasks": data.get("completed_subtasks", []),
    "files_modified": data.get("files_modified", []),
    "confidence": data.get("confidence", ""),
    "next_step": data.get("next_step", ""),
}
print(json.dumps(payload))
PY
)

curl -s -X POST http://localhost:8420/api/push/mcp-report \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
```

3. Report outcome:
   - If response contains `"ok": true`, confirm update posted.
   - If VibeCheck is unreachable, report that update was not saved.
   - If `status_label` is `"done"` and response indicates blocked completion, surface the reason and next action.

## Notes

- `status_label` must be one of: `planning`, `implementing`, `debugging`, `reviewing`, `done`
- Keep `summary` concise (1-2 sentences)
- Always include `files_modified` when files changed in this subtask
