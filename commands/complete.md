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

## Step 2 — Perform review

Run `/vibecheck:review` to perform the review. That command handles:
- fetching active Rulesets from VibeCheck (`/api/review-context`)
- analyzing the staged diff (falls back to working-tree diff vs HEAD when nothing is staged)
- attributing findings to Rulesets where applicable
- submitting findings to `/api/push/vc-review`

After `/vibecheck:review` completes, read its output to determine `ready_to_commit`.

If `ready_to_commit` is false, stop after reporting issue IDs/titles and do not proceed to Step 3.

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
