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

## Session Behavior Summary

Before evaluating process standards, reflect on your own behavior during this session. You have full access to your conversation history — use it.

Answer each question honestly based on what actually happened, not what should have happened:

- **Exploration before coding:** Did you read files (Read/Grep/Glob) before making your first edit? Roughly how many exploration calls preceded the first Write/Edit?
- **Verification after changes:** Did you run tests, linting, or other verification (Bash) after your last code change? What did you verify?
- **Focus discipline:** Compare the files you changed to the stated objective. Were all changes directly related, or did you drift into unrelated cleanup/refactoring?
- **Commit scope:** Is the set of changes a coherent, reviewable unit? Or does it bundle multiple unrelated concerns?
- **Specs for complex work:** For multi-file changes, was there a written plan or spec before implementation? Was Plan mode used?
- **Test-first for bugs:** If this was a bug fix, did you write a failing test before writing the fix? (Skip if this is feature work.)

---

## Active Standards

Fetch current review standards from VibeCheck before analyzing. Capture the output — you will need the standard IDs for the `rulesets_active` field in the payload, and the slug values for attributing findings.

!`curl -s --max-time 3 "http://localhost:8420/api/review-context?cwd=$(pwd)" \
  | python3 -c "
import json, sys
try:
    ctx = json.load(sys.stdin)
    standards = ctx.get('standards', [])
    rulesets = ctx.get('rulesets', [])
    if standards:
        print('STANDARDS_ACTIVE_IDS=' + json.dumps([s['id'] for s in standards]))
        print()
        # Print lookup table for building standard_evaluations
        print('STANDARDS_LOOKUP (id | slug | evidence_type):')
        for s in standards:
            print(f'  {s[\"id\"]} | {s[\"slug\"]} | {s.get(\"evidence_type\", \"code\")}')
        print()
        code_stds = [s for s in standards if s.get('evidence_type') in ('code', 'both')]
        process_stds = [s for s in standards if s.get('evidence_type') in ('process', 'both')]
        if code_stds:
            print('### Code Review Standards')
            for s in code_stds:
                print(f'- [{s[\"slug\"]}] {s[\"brief\"][:200]}')
            print()
        if process_stds:
            print('### Process Review Standards')
            for s in process_stds:
                print(f'- [{s[\"slug\"]}] {s[\"brief\"][:200]}')
            print()
    elif rulesets:
        print('RULESETS_ACTIVE_IDS=' + json.dumps([rs['id'] for rs in rulesets]))
        print()
        for rs in rulesets:
            print(f'### {rs[\"name\"]}')
            if rs.get('description'):
                print(f'*{rs[\"description\"]}*')
            for r in rs.get('rules', []):
                print(f'- [{r[\"slug\"]}] {r[\"instruction\"]}')
            print()
    else:
        print('(no standards or rulesets configured — using fallback criteria below)')
except Exception:
    print('(VibeCheck unreachable — using fallback criteria below)')
" 2>/dev/null`

## Fallback criteria (always apply if no Active Standards appear above)

Only flag issues in these categories:
- Correctness bugs (logic errors, off-by-one, wrong conditionals)
- Fragile assumptions (undefined behavior, type mismatches, missing null checks)
- Edge cases not handled (empty input, zero, negative numbers, concurrent access)
- Error handling gaps (uncaught exceptions, swallowed errors, missing rollbacks)
- Security or privacy risks (injection, hardcoded secrets, exposed sensitive data)
- Concurrency / race conditions
- Performance risks (O(n^2) in hot path, unbounded loops, unnecessary I/O)
- Breaking API changes (signature changes, removed fields, incompatible behavior)
- Missing validation (user input accepted without sanitization)
- Test quality (tautological tests, missing assertions, overly specific assertions)

**Do NOT include:** style nitpicks, naming preferences, documentation gaps, test coverage opinions (unless you can name a specific uncovered bug scenario).

If no meaningful issues exist, the review should be clean (ready_to_commit: true, empty blocking_issues).

---

## Instructions

This review has two passes. You MUST evaluate every active standard individually.

### Pass 1: Code Review

1. Review the diff above against all **Code Review Standards** (`evidence:code` and `evidence:both`).
2. For each code standard, determine: does the diff pass or fail? If fail, create a blocking issue.
3. Identify test gaps only where a specific uncovered scenario is risky.
4. Read additional file context with Read/Grep/Glob if needed to evaluate correctness.

### Pass 2: Process Review

5. Reflect on your own session behavior using the **Session Behavior Summary** prompts above. You are the session — use your conversation history to answer honestly.
6. For each process standard, determine: pass, fail, or not-applicable? Evaluate based on what you actually did:
   - `explore-before-coding`: Did you Read/Grep/Glob before your first Edit/Write?
   - `verify-your-work`: Did you run tests or linting (Bash) after your last code change?
   - `stay-focused`: Were all changed files related to the stated objective?
   - `test-first-for-bugs`: For bug-fix objectives, were tests written before the fix? (not-applicable for features)
   - `write-specs-for-complex-work`: For complex multi-file changes, was a spec or plan created first?
   - `commit-meaningful-units`: Is the diff a coherent, reviewable unit of work?
7. Process failures are NOT blocking issues — they are observations for improvement. Report them in `standard_evaluations` only.

### Finalize

8. Decide: is this safe to commit as-is? (only code issues block commits)
9. Build the `standard_evaluations` array: one entry per active standard, every standard must have a status.
10. Submit your findings to VibeCheck using the exact curl command below.
11. Parse the response and present a summary to the user (see "After submitting" below).

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
  "rulesets_active": ["<ids from STANDARDS_ACTIVE_IDS or RULESETS_ACTIVE_IDS above; use [] if VibeCheck was unreachable>"],
  "blocking_issues": [
    {
      "title": "<short title, max 80 chars>",
      "category": "<standard slug if from Active Standards; otherwise category name from Fallback list>",
      "severity": "High",
      "location": "<file.py:line or function name>",
      "problem": "<one sentence: what is wrong>",
      "why_risky": "<one sentence: what bad thing happens if this ships>",
      "concrete_fix": "<specific code change or approach>",
      "source_ruleset": "<Standard or Ruleset id if triggered by a named standard/rule; omit if from Fallback criteria>",
      "violated_rule": "<standard/rule slug exactly as it appeared in [brackets] above; omit if source_ruleset is omitted>"
    }
  ],
  "test_gaps": [
    {
      "name": "<test name>",
      "scenario": "<what condition to test>",
      "expected_behavior": "<what should happen>"
    }
  ],
  "standard_evaluations": [
    {
      "standard_id": "<standard UUID from STANDARDS_ACTIVE_IDS>",
      "slug": "<slug from [brackets] in Active Standards>",
      "status": "<pass | fail | not-applicable | not-evaluated>",
      "evidence_type": "<code | process | both>",
      "note": "<1 sentence: why this status>"
    }
  ],
  "ready_to_commit": false
}
```

Notes:
- Do not include an `id` field in blocking issues — the server assigns IDs automatically.
- `rulesets_active`: the list of standard or ruleset `id` values from the `STANDARDS_ACTIVE_IDS` or `RULESETS_ACTIVE_IDS` line above. If VibeCheck was unreachable, pass `[]`.
- `source_ruleset` / `violated_rule`: only include when a finding was specifically triggered by a named standard or rule from the Active Standards section. Omit both fields for findings from the Fallback criteria.
- `standard_evaluations`: **REQUIRED — one entry per active standard.** Every standard from the Active Standards section must have an evaluation. You always have access to your own session behavior, so `not-evaluated` should only be used for process standards when this review is run on changes from a different session. Use `not-applicable` when the standard doesn't apply to this type of work (e.g. `test-first-for-bugs` on a feature, not a bug fix). The `evidence_type` must match what was shown in the Active Standards section.

If there are no blocking issues: `"blocking_issues": [], "ready_to_commit": true`
If there are no test gaps: `"test_gaps": []`

---

## After submitting

Parse the JSON response from the curl command. The response includes an `issues` array with server-assigned IDs, titles, and severities.

**Always present the full standards report.** Use this exact format:

```
## Code Standards (N pass, M fail)
  ✓ correctness-bugs — No logic errors found in diff
  ✓ no-hardcoded-secrets — No credentials or tokens in diff
  ✗ race-condition-safety — TOCTOU pattern in archive_context
  ✓ security-privacy-risks — No injection or XSS vectors
  ... (every code standard, one line each)

## Process Standards (N pass, M fail, K not evaluated)
  ✓ explore-before-coding — 12 Read/Grep calls before first Edit
  ✗ verify-your-work — No test/lint run after final code change
  — test-first-for-bugs — Not applicable (feature, not bug fix)
  ? commit-meaningful-units — Transcript not available
  ... (every process standard, one line each)

## Blocking Issues (N)
  [id] Title (Severity) — location
  ...

Results logged to VibeCheck dashboard.
Would you like me to fix any of these?
```

Use `✓` for pass, `✗` for fail, `—` for not-applicable, `?` for not-evaluated.
Count only `pass` and `fail` as "evaluated" in the header. Show `not-evaluated` and `not-applicable` counts separately.

Then wait for the user's response. If the user says yes (for all or specific issues), use `/vibecheck:fix <ID>` for each one (ID is the internal VibeCheck issue ID).

**If VibeCheck is unreachable**, still show the full standards report, but note that results were not saved to the dashboard.

**If no blocking issues were found**, still show the full standards report, then tell the user the changes are ready to commit.
