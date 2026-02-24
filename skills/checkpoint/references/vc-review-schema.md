# VcReview Payload Schema

POST to `http://localhost:8420/api/push/vc-review`.

```json
{
  "session_id": "<CLAUDE_SESSION_ID or 'unknown'>",
  "cwd": "<absolute path to working directory>",
  "staged_files": ["<file1>", "<file2>"],
  "blocking_issues": [
    {
      "title": "<short title, max 80 chars>",
      "category": "<one of the review criteria below>",
      "severity": "High",
      "location": "<file.py:line or function name>",
      "problem": "<one sentence: what is wrong>",
      "why_risky": "<one sentence: what bad thing happens if this ships>",
      "concrete_fix": "<specific code change or approach>"
    }
  ],
  "test_gaps": [
    {
      "name": "<test name>",
      "scenario": "<what condition to test>",
      "expected_behavior": "<what should happen>"
    }
  ],
  "ready_to_commit": false
}
```

## Field notes

- `session_id`: use `${CLAUDE_SESSION_ID:-unknown}` in bash or `"unknown"` if unavailable
- `cwd`: use `pwd` output — the server derives the project name from this value
- `staged_files`: the scoped file list from the reviewing procedure (Steps 1–2); must match the files in the diff
- `severity`: `"High"` = must fix before commit; `"Medium"` = important but not blocking
- `ready_to_commit`: `true` only when `blocking_issues` is empty
- If no blocking issues: `"blocking_issues": [], "ready_to_commit": true`
- If no test gaps: `"test_gaps": []`
- Do NOT include an `id` field in blocking issues — the server assigns project-prefixed labels (e.g. `VC-7`) automatically

## Server response

The server returns a JSON object including an `issues` array with the server-assigned labels:

```json
{
  "ok": true,
  "blocking_issues": 2,
  "test_gaps": 0,
  "ready_to_commit": false,
  "alerts_created": 3,
  "issues": [
    {"id": "B1", "title": "Missing null check in handleUserInput", "severity": "High", "location": "src/handler.py:42"},
    {"id": "B2", "title": "SQL query vulnerable to injection", "severity": "High", "location": "src/db.py:87"}
  ]
}
```

Use the `issues` array to present findings to the user and ask if they want specific issues fixed.

## Valid `category` values

- `Correctness bugs`
- `Fragile assumptions`
- `Edge cases not handled`
- `Error handling gaps`
- `Security or privacy risks`
- `Concurrency / race conditions`
- `Performance risks`
- `Breaking API changes`
- `Missing validation`

## Example curl command

```bash
curl -s -X POST http://localhost:8420/api/push/vc-review \
  -H "Content-Type: application/json" \
  -d '<YOUR_JSON_PAYLOAD>'
```

If VibeCheck is not running, the curl will fail silently — that is acceptable. Still show the user your findings.
