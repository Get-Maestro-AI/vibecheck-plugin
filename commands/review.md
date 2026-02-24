---
description: Review staged changes for bugs before committing
allowed-tools: Bash, Read, Grep, Glob
---

You will perform a focused pre-commit code review of staged changes and report findings to the VibeCheck dashboard.

**Your job is NOT general feedback. Your job is: find real problems that should be fixed before this commit.**

> **IMPORTANT: Do not make any code changes during this review.** Your only action is to analyze the diff, POST findings to VibeCheck, and present results to the user. Fixes happen separately, after the user decides which issues to address.

---

## Staged changes

Staged files:
!`git diff --cached --name-only 2>/dev/null || echo "(no staged files)"`

Diff:
!`git diff --cached 2>/dev/null || echo "(empty diff)"`

---

## Review criteria

Only flag issues in these categories:
- Correctness bugs (logic errors, off-by-one, wrong conditionals)
- Fragile assumptions (undefined behavior, type mismatches, missing null checks)
- Edge cases not handled (empty input, zero, negative numbers, concurrent access)
- Error handling gaps (uncaught exceptions, swallowed errors, missing rollbacks)
- Security or privacy risks (injection, hardcoded secrets, exposed sensitive data)
- Concurrency / race conditions
- Performance risks (O(n²) in hot path, unbounded loops, unnecessary I/O)
- Breaking API changes (signature changes, removed fields, incompatible behavior)
- Missing validation (user input accepted without sanitization)

**Do NOT include:** style nitpicks, naming preferences, documentation gaps, test coverage opinions (unless you can name a specific uncovered bug scenario).

If no meaningful issues exist, the review should be clean (ready_to_commit: true, empty blocking_issues).

---

## Instructions

1. Review the staged diff above. Read additional file context with Read/Grep/Glob if needed to evaluate correctness.
2. Identify blocking issues. For each, determine: severity (High = must fix before commit, Medium = important but not blocking), exact location, and a concrete fix.
3. Identify test gaps only where a specific uncovered scenario is risky.
4. Decide: is this safe to commit as-is?
5. Submit your findings to VibeCheck using the exact curl command below.
6. Parse the response and present a summary to the user (see "After submitting" below).

**Constructing the curl payload:**
Build the JSON payload with your actual findings, then run this curl command:

```bash
curl -s -X POST http://localhost:8420/api/push/vc-review \
  -H "Content-Type: application/json" \
  -d '<YOUR_JSON_PAYLOAD>'
```

The JSON payload structure:
```json
{
  "session_id": "!`echo ${CLAUDE_SESSION_ID:-unknown}`",
  "cwd": "!`pwd`",
  "staged_files": ["<from staged files list above>"],
  "blocking_issues": [
    {
      "title": "<short title, max 80 chars>",
      "category": "<from the review criteria list>",
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

Note: do not include an `id` field in blocking issues — the server assigns IDs automatically.

If there are no blocking issues: `"blocking_issues": [], "ready_to_commit": true`
If there are no test gaps: `"test_gaps": []`

---

## After submitting

Parse the JSON response from the curl command. The response includes an `issues` array with server-assigned IDs, titles, and severities.

**If VibeCheck is reachable and issues were found**, present a summary like this:

```
VibeCheck found 2 blocking issue(s):
  [401] Missing null check in handleUserInput (High) — src/handler.py:42
  [402] SQL query vulnerable to injection (High) — src/db.py:87

These have been logged to the VibeCheck dashboard.
Would you like me to fix any of these?
```

Then wait for the user's response. If the user says yes (for all or specific issues), use `/vibecheck:fix <ID>` for each one (ID is the internal VibeCheck alert ID).

**If VibeCheck is unreachable**, still show the user your findings in the same format, but note that they were not saved to the dashboard.

**If no blocking issues were found**, tell the user the staged changes look clean and are ready to commit.
