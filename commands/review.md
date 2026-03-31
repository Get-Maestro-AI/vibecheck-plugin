---
description: Review phase quality check — routes to review-phase skills (security, architecture, code, etc.) based on changed files
allowed-tools: Bash, Read, Grep, Glob
---

You will perform a focused quality check of your recent work and report findings to the VibeCheck dashboard.

**Your job is NOT general feedback. Your job is: find real problems that should be fixed before moving on.**

> **IMPORTANT: Do not make any code changes during this check.** Your only action is to analyze the work, discover relevant check skills, POST findings to VibeCheck, and present results to the user. Fixes happen separately, after the user decides which issues to address.

**Scope:** The context below is automatically scoped to the current session's objective and phase when available. If no objective was found, it falls back to staged or uncommitted changes.

---

## Phase 1 — Gather context and detect development phase

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

# -- 1. Fetch objective context + phase signals from VibeCheck --
obj_files = []
obj_started_at = ""
obj_title = ""
pipeline_phase = ""
status_label = ""
current_task = ""
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
    pipeline_phase = ctx.get("pipeline_phase") or ""
    status_label = ctx.get("status_label") or ""
    current_task = ctx.get("current_task") or ""
except Exception:
    pass

# -- 2. Print phase context --
if pipeline_phase:
    print(f"Pipeline phase: {pipeline_phase}")
if status_label:
    print(f"Work phase: {status_label}")
if current_task:
    print(f"Task: {current_task}")
if obj_title:
    print(f"Objective: {obj_title}")
if status_label or current_task or obj_title:
    print()

def git(*args):
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True, cwd=cwd)
    return r.stdout.strip()

# -- 3. Build diff (for implementation/code phases) --
if obj_files:
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

# -- 4. File-pattern routing heuristics (fallback signal) --
import re

code_exts = {'.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs'}
design_exts = {'.tsx', '.jsx', '.css', '.scss'}
arch_patterns = [r'models\.py$', r'routers/', r'state/', r'alembic/', r'db/']
product_exts = {'.md'}

check_types = set()
md_count = 0

for f in changed_files:
    ext = os.path.splitext(f)[1].lower()
    if ext in code_exts:
        check_types.add("code-check")
    if ext in design_exts or 'frontend/' in f:
        check_types.add("design-check")
    if any(re.search(p, f) for p in arch_patterns):
        check_types.add("architecture-check")
    if ext in product_exts:
        md_count += 1

if changed_files and md_count > len(changed_files) * 0.5:
    check_types.add("product-check")
for f in changed_files:
    base_name = os.path.basename(f).lower()
    if base_name in ('readme.md', 'claude.md') or 'docs/' in f:
        check_types.add("product-check")
        break

if not check_types:
    check_types.add("code-check")

print()
print("Heuristic check types: " + ", ".join(sorted(check_types)))
print("Pipeline phase: " + (pipeline_phase or "(none)"))
print("Work phase: " + (status_label or "(none)"))
print("Current task: " + (current_task or "(none)"))
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

## Phase 2 — Discover and load check skills

Route to check skills using the **heuristic check types** from Phase 1 output. `vibe:review` routes only within the Review phase — it discovers review-type skills (security, architecture, code, design, etc.) based on the files changed.

> **Note:** `vibe:review` is scoped to quality checks only. For spec shaping use `vibe:think`, for plan review use `vibe:plan`, for build guidance use `vibe:build`. Each phase has its own command.

Read the "Heuristic check types" line from Phase 1. Use it to build the discovery query:

```
vibecheck_discover(query="review <heuristic check types from Phase 1>", layer="skill", skill_type="review", situation="Review phase — reviewing <summary of changes>", limit=4)
```

**For every skill returned, you MUST call `vibecheck_get(id)` to load the full brief.** Do not rely on the context_summary snippet from the discover result — it is not the methodology, it is a description of when to use the skill. Do not skip this step because you already know what "security check" or "code check" means. The brief defines the specific methodology to follow; your general knowledge does not substitute for it.

**Merge logic:**
- `code-check` is always required when the diff contains any code files (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.go`, `.rs`, etc.). Do not drop it because a more specific check type was discovered.
- Union all heuristic check types — do not pick one, run **all** that apply.
- For each check type in the final set: if a skill brief was loaded for that type, follow its methodology. Otherwise use the Built-in Check Criteria.
- Run each type in sequence; all findings across all passes go into the single payload.
- If no skills are found at all, fall back to the Built-in Check Criteria for every type.

---

## Phase 3 — Execute checks and report

### Check execution

**You must run every check type in the set — not just the most interesting one.** If the set is `{code-check, security-check}`, run both in full before submitting.

For each check type identified in Phase 2:
1. If a skill brief was loaded for this type, follow its methodology
2. Otherwise, use the Built-in Check Criteria below
3. Tag each finding with the check type that produced it (in the `category` field)

Read additional file context with Read/Grep/Glob if needed to evaluate correctness.

### Built-in Check Criteria (fallback — use when no skill is loaded for a check type)

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

If no meaningful issues exist, the check should be clean (ready_to_commit: true, empty blocking_issues).

---

## Finalize and submit

1. Decide: is this safe to move forward as-is?
2. Submit findings using `vibecheck_push_review` — session_id and cwd are resolved automatically.
3. Parse the response and present a summary to the user.

```
vibecheck_push_review(
  staged_files=["<from Reviewed files list above>"],
  blocking_issues=[
    {
      "title": "<short title, max 80 chars>",
      "category": "<check type, e.g. code-check, design-check>",
      "severity": "High",           # Critical | High | Medium | Low
      "location": "<file.py:line>",
      "problem": "<one sentence: what is wrong>",
      "why_risky": "<one sentence: what bad thing happens if this ships>",
      "concrete_fix": "<specific code change or approach>"
    }
  ],
  test_gaps=[
    {
      "name": "<test name>",
      "scenario": "<what condition to test>",
      "expected_behavior": "<what should happen>"
    }
  ],
  ready_to_commit=False
)
```

Notes:
- If there are no blocking issues: `blocking_issues=[], ready_to_commit=True`
- If there are no test gaps: `test_gaps=[]`

---

## After submitting

Parse the JSON response from `vibecheck_push_review`. The response includes an `issues` array with server-assigned IDs, titles, and severities.

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

Then wait for the user's response. If the user says yes (for all or specific issues), use `/vibe:fix <ID>` for each one (ID is the internal VibeCheck issue ID).

**If VibeCheck is unreachable**, show findings but note results were not saved to the dashboard.

**If no blocking issues were found**, tell the user the changes are ready to commit.

---

## Summarise findings

After presenting the results table, output a single-line status summary using ANSI color codes.
Parse `ftx_just_completed` from the `vibecheck_push_review` tool response.

Use this 6-state table to select the right output:

| Condition | Symbol | Line 1 | Line 2 |
|---|---|---|---|
| Clean, no prior issues — FTX first cycle | `✓` green | `Clean check. No issues found.` | `One down.` |
| Clean, no issues — normal | `✓` green | `Clean check. No issues found.` | — |
| Non-blocking issues only (test gaps, suggestions) | `△` yellow | `Check complete. N suggestions — nothing blocking.` | `Fix them when you're ready.` |
| Blocking issues found | `✗` red | `N blocking issues found.` | `Not done yet.` |
| Clean after prior blocking issues — FTX | `✓` green | `Clean check. All issues resolved.` | `Loop closed.` |
| Clean after prior blocking issues — normal | `✓` green | `Clean check. All issues resolved.` | — |

**Selection logic:**
- `ftx_just_completed: true` → use the FTX variant of the matching clean state
- `ready_to_commit: true` and `blocking_issues: 0` and no test_gaps → "Clean, no issues"
- `ready_to_commit: true` and `blocking_issues: 0` and `ftx_just_completed: true` → "All issues resolved — FTX" (ftx fires only when ≥1 issue was resolved this session)
- `test_gaps > 0` and `blocking_issues: 0` → "Non-blocking issues"
- `blocking_issues > 0` → "Blocking issues"

**ANSI codes:** green = `\033[32m`, yellow = `\033[33m`, red = `\033[31m`, reset = `\033[0m`

Print the summary to the terminal using a `Bash` echo command with `-e` flag for ANSI codes. Example for the clean state:

```bash
echo -e "\033[32m✓ Clean check. No issues found.\033[0m"
```
