---
description: Review recent changes — routes to specialized review skills based on context
allowed-tools: Bash, Read, Grep, Glob
---

You will perform a focused review of your recent changes and report findings to the VibeCheck dashboard.

**Your job is NOT general feedback. Your job is: find real problems that should be fixed before this commit.**

> **IMPORTANT: Do not make any code changes during this review.** Your only action is to analyze the diff, discover relevant review skills, POST findings to VibeCheck, and present results to the user. Fixes happen separately, after the user decides which issues to address.

**Scope:** The diff below is automatically scoped to the current session's objective when available. If no objective was found, it falls back to staged or uncommitted changes. If the diff shown below doesn't match the work you've been doing in this session, use your own judgment — review your recent changes by examining `git diff HEAD` or `git diff` for the files you actually modified.

---

## Phase 1 — Gather context and route

!`python3 - <<'PY'
import json, os, subprocess, urllib.request, urllib.parse

cwd = os.getcwd()
session_id = os.environ.get("CLAUDE_SESSION_ID", "")

vc_url = os.environ.get("VIBECHECK_API_URL", "").strip().rstrip("/")
if not vc_url:
    try:
        with open(os.path.expanduser("~/.config/vibecheck/config")) as _f:
            for _ln in _f:
                if _ln.startswith("api_url="):
                    vc_url = _ln.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
if not vc_url:
    vc_url = "http://localhost:8420"

# -- 1. Fetch objective context from VibeCheck --
obj_files = []
obj_started_at = ""
obj_title = ""
try:
    params = {"cwd": cwd}
    if session_id:
        params["session_id"] = session_id
    url = vc_url + "/api/review-context?" + urllib.parse.urlencode(params)
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

# -- 2. Build diff --
if obj_files:
    print(f"Objective: {obj_title}")
    print(f"Files changed during objective ({len(obj_files)}):")
    for f in obj_files:
        print(f"  {f}")
    print()

    base = ""
    if obj_started_at:
        base = git("log", f"--before={obj_started_at}", "--format=%H", "-1")
    if not base:
        all_commits = git("log", "--format=%H").splitlines()
        base = all_commits[9] if len(all_commits) >= 10 else (all_commits[-1] if all_commits else "")

    committed = ""
    if base:
        committed = git("diff", f"{base}..HEAD", "--", *obj_files)
    uncommitted = git("diff", "HEAD", "--", *obj_files)

    if committed:
        print("### Committed changes (since objective started)")
        print(committed[:60000])
        print()
    if uncommitted:
        print("### Uncommitted changes (staged / working tree)")
        print(uncommitted[:20000])
        print()
    if not committed and not uncommitted:
        print("(no diff found for objective files -- showing HEAD diff as fallback)")
        print(git("diff", "HEAD") or "(empty diff)")
    changed_files = obj_files
else:
    print("(No current objective found for this session -- showing recent changes)")
    print()
    staged = git("diff", "--cached")
    if staged:
        print("### Staged changes")
        print(staged[:60000])
    else:
        fallback = git("diff", "HEAD")
        print(fallback[:60000] if fallback else "(empty diff)")
    staged_names = git("diff", "--cached", "--name-only")
    changed_files = (staged_names if staged_names else git("diff", "--name-only", "HEAD")).splitlines()

# -- 3. File-pattern routing heuristics --
import re

code_exts = {'.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs'}
design_exts = {'.tsx', '.jsx', '.css', '.scss'}
arch_patterns = [r'models\.py$', r'routers/', r'state/', r'alembic/', r'db/']
product_exts = {'.md'}

review_types = set()
md_count = 0

for f in changed_files:
    ext = os.path.splitext(f)[1].lower()
    if ext in code_exts:
        review_types.add("code-review")
    if ext in design_exts or 'frontend/' in f:
        review_types.add("design-review")
    if any(re.search(p, f) for p in arch_patterns):
        review_types.add("architecture-review")
    if ext in product_exts:
        md_count += 1

if changed_files and md_count > len(changed_files) * 0.5:
    review_types.add("product-review")
for f in changed_files:
    base_name = os.path.basename(f).lower()
    if base_name in ('readme.md', 'claude.md') or 'docs/' in f:
        review_types.add("product-review")
        break

if not review_types:
    review_types.add("code-review")

print()
print("Suggested review types: " + ", ".join(sorted(review_types)))
PY
`

Reviewed files:
!`python3 - <<'PY'
import json, os, subprocess, urllib.request, urllib.parse

cwd = os.getcwd()
session_id = os.environ.get("CLAUDE_SESSION_ID", "")

vc_url = os.environ.get("VIBECHECK_API_URL", "").strip().rstrip("/")
if not vc_url:
    try:
        with open(os.path.expanduser("~/.config/vibecheck/config")) as _f:
            for _ln in _f:
                if _ln.startswith("api_url="):
                    vc_url = _ln.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
if not vc_url:
    vc_url = "http://localhost:8420"

obj_files = []
try:
    params = {"cwd": cwd}
    if session_id:
        params["session_id"] = session_id
    url = vc_url + "/api/review-context?" + urllib.parse.urlencode(params)
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

## Phase 2 — Discover and load review skills

Now route to the right review methodology. Two signals to merge:

**Signal A** (above): The "Suggested review types" line from file-pattern heuristics.

**Signal B**: Call `vibecheck_discover` to find matching review skills. Use `skill_type="review"` to pull all skills registered as review skills:

```
vibecheck_discover(query="review <objective_title or summary of changes>", layer="skill", skill_type="review", limit=4)
```

Then for each relevant result, load the full skill brief with `vibecheck_get_context(id)`.

**Merge logic:**
- **`code-review` is always required** when the diff contains any code files (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, etc.). Do not drop it because a more specific review type was discovered.
- Union Signal A and Signal B — do not pick one type, run **all** that apply. "Security changes were found" does not replace code-review; it adds to it.
- For each review type in the final set: if a skill brief was loaded for that type, follow its methodology. Otherwise use the Built-in Review Criteria.
- Run each type in sequence; all findings across all passes go into the single payload.
- If no skills are found at all, fall back to the Built-in Review Criteria for every type.

---

## Phase 3 — Execute review and report

### Review execution

**You must run every review type in the set — not just the most interesting one.** If the set is `{code-review, security-review}`, run both in full before submitting.

For each review type identified in Phase 2:
1. If a skill brief was loaded for this type, follow its methodology
2. Otherwise, use the Built-in Review Criteria below
3. Tag each finding with the review type that produced it (in the `category` field)

Read additional file context with Read/Grep/Glob if needed to evaluate correctness.

### Built-in Review Criteria (fallback — use when no skill is loaded for a review type)

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

## Finalize and submit

1. Decide: is this safe to commit as-is?
2. Submit findings to VibeCheck using the exact curl command below.
3. Parse the response and present a summary to the user.

**Constructing the curl payload:**
Build the JSON payload with your actual findings, then run this curl command:

```bash
_VC_CONF="$HOME/.config/vibecheck/config"
_VC_KEY="${VIBECHECK_API_KEY:-$(grep '^api_key=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
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
  "blocking_issues": [
    {
      "title": "<short title, max 80 chars>",
      "category": "<review type that produced this finding, e.g. code-review, design-review>",
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

Notes:
- Do not include an `id` field in blocking issues — the server assigns IDs automatically.
- If there are no blocking issues: `"blocking_issues": [], "ready_to_commit": true`
- If there are no test gaps: `"test_gaps": []`

---

## After submitting

Parse the JSON response from the curl command. The response includes an `issues` array with server-assigned IDs, titles, and severities.

Present results in this format:

```
## Blocking Issues (N)
  [id] Title (Severity) — location
  ...

## Test Gaps (N)
  - scenario
  ...

Results logged to VibeCheck dashboard.
Would you like me to fix any of these?
```

Then wait for the user's response. If the user says yes (for all or specific issues), use `/vibecheck:fix <ID>` for each one (ID is the internal VibeCheck issue ID).

**If VibeCheck is unreachable**, show findings but note results were not saved to the dashboard.

**If no blocking issues were found**, tell the user the changes are ready to commit.
