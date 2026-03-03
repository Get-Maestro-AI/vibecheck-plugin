---
description: Review staged (or working-tree) changes for bugs before committing
allowed-tools: Bash, Read, Grep, Glob
---

You will perform a focused pre-commit code review of staged changes and report findings to the VibeCheck dashboard.

**Your job is NOT general feedback. Your job is: find real problems that should be fixed before this commit.**

> **IMPORTANT: Do not make any code changes during this review.** Your only action is to analyze the diff, POST findings to VibeCheck, and present results to the user. Fixes happen separately, after the user decides which issues to address.

---

## Changes to review

!`python3 - <<'PY'
import json, os, subprocess, urllib.request, urllib.parse

cwd = os.getcwd()

# ── 1. Fetch objective context from VibeCheck ────────────────────────────────
obj_files = []
obj_started_at = ""
obj_title = ""
try:
    url = "http://localhost:8420/api/review-context?" + urllib.parse.urlencode({"cwd": cwd})
    resp = urllib.request.urlopen(url, timeout=3)
    ctx = json.loads(resp.read())
    obj_files = ctx.get("objective_files") or []
    obj_started_at = ctx.get("objective_started_at") or ""
    obj_title = ctx.get("objective_title") or ""
except Exception:
    pass

def git(*args):
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True, cwd=cwd)
    return r.stdout.strip()

# ── 2. Build diff ─────────────────────────────────────────────────────────────
if obj_files:
    print(f"Objective: {obj_title}")
    print(f"Files changed during objective ({len(obj_files)}):")
    for f in obj_files:
        print(f"  {f}")
    print()

    # Find the commit that was HEAD just before the objective started
    base = ""
    if obj_started_at:
        base = git("log", f"--before={obj_started_at}", "--format=%H", "-1")

    # Fall back to 10-commit lookback if timestamp lookup fails
    if not base:
        all_commits = git("log", "--format=%H").splitlines()
        base = all_commits[9] if len(all_commits) >= 10 else (all_commits[-1] if all_commits else "")

    # Committed changes to objective files since base
    committed = ""
    if base:
        committed = git("diff", f"{base}..HEAD", "--", *obj_files)

    # Any uncommitted changes (staged or unstaged) to those files
    uncommitted = git("diff", "HEAD", "--", *obj_files)

    if committed:
        print("### Committed changes (since objective started)")
        print(committed[:60000])  # cap at ~60KB
        print()
    if uncommitted:
        print("### Uncommitted changes (staged / working tree)")
        print(uncommitted[:20000])
        print()
    if not committed and not uncommitted:
        print("(no diff found for objective files — showing HEAD diff as fallback)")
        print(git("diff", "HEAD") or "(empty diff)")
else:
    # Fallback: staged → working tree vs HEAD
    print("(No objective file list available — falling back to staged/HEAD diff)")
    print()
    staged = git("diff", "--cached")
    if staged:
        print("### Staged changes")
        print(staged[:60000])
    else:
        fallback = git("diff", "HEAD")
        print(fallback[:60000] if fallback else "(empty diff)")
PY
`

Reviewed files:
!`python3 - <<'PY'
import json, os, subprocess, urllib.request, urllib.parse

cwd = os.getcwd()
obj_files = []
try:
    url = "http://localhost:8420/api/review-context?" + urllib.parse.urlencode({"cwd": cwd})
    resp = urllib.request.urlopen(url, timeout=3)
    ctx = json.loads(resp.read())
    obj_files = ctx.get("objective_files") or []
except Exception:
    pass

if obj_files:
    for f in obj_files:
        print(f)
else:
    def git(*args):
        r = subprocess.run(["git"] + list(args), capture_output=True, text=True, cwd=cwd)
        return r.stdout.strip()
    staged = git("diff", "--cached", "--name-only")
    print(staged if staged else git("diff", "--name-only", "HEAD") or "(no changes)")
PY
`

---

## Active Rulesets

Fetch current Rulesets from VibeCheck before analyzing. Capture the output — you will need the `id` values for the `rulesets_active` field in the payload.

!`curl -s --max-time 3 "http://localhost:8420/api/review-context?cwd=$(pwd)" \
  | python3 -c "
import json, sys
try:
    ctx = json.load(sys.stdin)
    rulesets = ctx.get('rulesets', [])
    if not rulesets:
        print('(no custom rulesets configured — using fallback criteria below)')
    else:
        print('RULESETS_ACTIVE_IDS=' + json.dumps([rs['id'] for rs in rulesets]))
        print()
        for rs in rulesets:
            print(f'### {rs[\"name\"]}')
            if rs.get('description'):
                print(f'*{rs[\"description\"]}*')
            for r in rs.get('rules', []):
                print(f'- [{r[\"slug\"]}] {r[\"instruction\"]}')
            print()
except Exception:
    print('(VibeCheck unreachable — using fallback criteria below)')
" 2>/dev/null`

## Fallback criteria (always apply if no Active Rulesets appear above)

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

1. Review the diff above (objective files diffed from their base commit when VibeCheck is available; otherwise staged changes or working-tree vs HEAD). Read additional file context with Read/Grep/Glob if needed to evaluate correctness.
2. Identify blocking issues. For each, determine: severity (High = must fix before commit, Medium = important but not blocking), exact location, and a concrete fix.
3. Identify test gaps only where a specific uncovered scenario is risky.
4. Decide: is this safe to commit as-is?
5. Submit your findings to VibeCheck using the exact curl command below.
6. Parse the response and present a summary to the user (see "After submitting" below).

**Constructing the curl payload:**
Build the JSON payload with your actual findings, then run this curl command:

```bash
_VC_CONF="$HOME/.config/vibecheck/config.json"
_VC_KEY="${VIBECHECK_API_KEY:-$(sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"
_VC_URL="${VIBECHECK_API_URL:-$(sed -n 's/.*"api_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"
_VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"
_AUTH_ARGS=()
[ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY")

curl -s -X POST "$_VC_URL/api/push/vc-review" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d '<YOUR_JSON_PAYLOAD>'
```

The JSON payload structure:
```json
{
  "session_id": "!`echo ${CLAUDE_SESSION_ID:-unknown}`",
  "cwd": "!`pwd`",
  "staged_files": ["<from Reviewed files list above>"],
  "rulesets_active": ["<ids from RULESETS_ACTIVE_IDS above; use [] if VibeCheck was unreachable>"],
  "blocking_issues": [
    {
      "title": "<short title, max 80 chars>",
      "category": "<rule slug if from Active Rulesets; otherwise category name from Fallback list>",
      "severity": "High",
      "location": "<file.py:line or function name>",
      "problem": "<one sentence: what is wrong>",
      "why_risky": "<one sentence: what bad thing happens if this ships>",
      "concrete_fix": "<specific code change or approach>",
      "source_ruleset": "<Ruleset id if this finding was triggered by a named rule; omit if from Fallback criteria>",
      "violated_rule": "<rule slug exactly as it appeared in [brackets] above; omit if source_ruleset is omitted>"
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

Notes:
- Do not include an `id` field in blocking issues — the server assigns IDs automatically.
- `rulesets_active`: the list of Ruleset `id` values from the `RULESETS_ACTIVE_IDS` line above. If VibeCheck was unreachable or returned no rulesets, pass `[]`.
- `source_ruleset` / `violated_rule`: only include when a finding was specifically triggered by a named rule from the Active Rulesets section. Omit both fields for findings from the Fallback criteria.

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
