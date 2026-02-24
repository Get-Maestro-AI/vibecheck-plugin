---
description: Wrap up the current task: review code and mark the objective done
allowed-tools: Bash, Read, Grep, Glob
---

Run the VibeCheck completion protocol for the current objective.

Optional argument:
- `$ARGUMENTS` may contain an explicit objective ID (recommended when available).

## Non-negotiable flow

1. `begin_completion` must succeed before review starts.
2. Review findings must be submitted to VibeCheck (`/api/push/vc-review`).
3. Finalize is attempted only when review says `ready_to_commit: true`.

If any step fails, stop and report the blocking reason.

---

## Step 1 — Begin completion

Run:

```bash
OBJ_ID="$ARGUMENTS"
export OBJ_ID
if [ -n "$OBJ_ID" ]; then
  BEGIN_PAYLOAD=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
  "cwd": os.getcwd(),
  "objective_id": os.environ.get("OBJ_ID", ""),
  "trigger": "manual",
}))
PY
)
else
  BEGIN_PAYLOAD=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
  "cwd": os.getcwd(),
  "trigger": "manual",
}))
PY
)
fi

BEGIN_RESPONSE=$(curl -s -X POST http://localhost:8420/api/push/begin-completion \
  -H "Content-Type: application/json" \
  -d "$BEGIN_PAYLOAD")
echo "$BEGIN_RESPONSE"
```

If begin returns blocked, stop and report the reason.

---

## Step 2 — Perform review and submit findings

Use the same correctness-focused criteria and payload schema as `/vibecheck:review`:
- analyze staged diff (`git diff --cached`)
- produce blocking issues only for real pre-commit risks
- submit findings to:

```bash
curl -s -X POST http://localhost:8420/api/push/vc-review \
  -H "Content-Type: application/json" \
  -d '<REVIEW_JSON_PAYLOAD>'
```

The payload must include:
- `session_id`, `cwd`, `staged_files`
- `blocking_issues` (possibly empty)
- `test_gaps` (possibly empty)
- `ready_to_commit` (boolean)

Print the response JSON from `vc-review`.

If `ready_to_commit` is false, stop after reporting issue IDs/titles and do not finalize.

---

## Step 3 — Finalize objective (only when review is clean)

Run:

```bash
FINALIZE_PAYLOAD=$(python3 - <<'PY'
import json, os
payload = {
  "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
  "cwd": os.getcwd(),
  "checkpoint_summary": "Objective finalized after successful pre-commit review.",
}
obj = os.environ.get("OBJ_ID", "").strip()
if obj:
    payload["objective_id"] = obj
print(json.dumps(payload))
PY
)

FINALIZE_RESPONSE=$(curl -s -X POST http://localhost:8420/api/push/finalize-objective \
  -H "Content-Type: application/json" \
  -d "$FINALIZE_PAYLOAD")
echo "$FINALIZE_RESPONSE"
```

Report one of:
- finalized successfully
- blocked (with reason and next_action)
- request failed (server unreachable/invalid response)
