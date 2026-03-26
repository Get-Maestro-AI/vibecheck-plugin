---
description: Plan your current task — routes to a specialist planning skill based on context
allowed-tools: Bash, Read, Grep, Glob
---

You will produce a structured implementation plan for your current task and enter plan mode with the result.

**Your job is to choose the right planning approach for the context, not to improvise a generic plan.** The specialist skill defines the methodology; your general knowledge does not substitute for it.

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

# -- 1. Fetch plan context from VibeCheck --
ctx = {}
try:
    params = {"cwd": cwd}
    if session_id:
        params["session_id"] = session_id
    url = vc_url + "/api/plan-context?" + urllib.parse.urlencode(params)
    resp = urllib.request.urlopen(url, timeout=3)
    ctx = json.loads(resp.read())
except Exception:
    pass

objective_title = ctx.get("objective_title") or ""
active_spec_id = ctx.get("active_spec_id") or ""
active_issue_id = ctx.get("active_issue_id") or ""
changed_files = ctx.get("changed_files") or []
git_branch = ctx.get("git_branch") or ""
saved_plan = ctx.get("saved_plan")

if objective_title:
    print(f"Objective: {objective_title}")
if active_spec_id:
    print(f"Active spec: {active_spec_id}")
if active_issue_id:
    print(f"Active issue: {active_issue_id}")
if git_branch:
    print(f"Branch: {git_branch}")
if changed_files:
    print(f"Changed files ({len(changed_files)}):")
    for f in changed_files[:10]:
        print(f"  {f}")
    if len(changed_files) > 10:
        print(f"  ... and {len(changed_files) - 10} more")
print()

# -- 2. Resume check --
if saved_plan:
    done = saved_plan.get("steps_done", 0)
    total = saved_plan.get("steps_total", 0)
    plan_id = saved_plan.get("plan_id", "")
    plan_title = saved_plan.get("title", "")
    print(f"SAVED PLAN FOUND: {plan_id}")
    print(f"  Title: {plan_title}")
    print(f"  Progress: {done}/{total} steps complete")
    print(f"  Created: {saved_plan.get('created_at', '')}")
    print()
    print("You may resume this plan or create a new one.")
    print()

# -- 3. File-pattern routing heuristics --
import os, re

code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
design_exts = {".tsx", ".jsx", ".css", ".scss"}
arch_patterns = [r"models\.py$", r"routers/", r"state/", r"alembic/", r"db/"]

plan_type = ""
new_file_count = 0
existing_file_count = 0

title_lower = (objective_title or "").lower()
debug_words = {"fix", "debug", "error", "broken", "not working", "issue", "bug", "failing"}
if any(w in title_lower for w in debug_words):
    plan_type = "debug-plan"

if not plan_type:
    for f in changed_files:
        ext = os.path.splitext(f)[1].lower()
        if any(re.search(p, f) for p in arch_patterns):
            plan_type = "architecture-plan"
            break
        if ext in design_exts or "frontend/" in f:
            plan_type = "design-plan"
            break

if not plan_type:
    has_code = any(os.path.splitext(f)[1].lower() in code_exts for f in changed_files)
    if active_spec_id and not changed_files:
        plan_type = "product-plan"
    elif active_spec_id and has_code:
        plan_type = "feature-plan"
    elif changed_files and has_code:
        plan_type = "refactor-plan"

if not plan_type:
    plan_type = "feature-plan"

# Accept override or free-text description from $ARGUMENTS
import sys
arg = "$ARGUMENTS".strip()
if arg and arg.endswith("-plan"):
    plan_type = arg
    print(f"Plan type overridden by argument: {plan_type}")
elif arg:
    # Free-text task description (e.g. /vibecheck:plan "I want to build X")
    # Use as objective title if no session objective exists
    if not objective_title:
        objective_title = arg
    print(f"Task description: {arg}")

print(f"Suggested plan type: {plan_type}")
print(f"Has spec: {'yes' if active_spec_id else 'no'}")
print(f"Has saved plan: {'yes' if saved_plan else 'no'}")
PY
`

---

## Phase 1b — Classify task scope

Before proceeding, classify this task as **BOUNDED** or **OPEN** using the output from Phase 1.

**BOUNDED — proceed directly to Phase 2:**
- Scope is fully defined (you could write all acceptance criteria right now)
- Single system or module; no unresolved UX or design decisions
- Could be completed in one session with no open questions

**OPEN — consider shaping first:**
- Requirements are ambiguous, incomplete, or still being negotiated
- Involves user-facing design decisions, new data models, multiple systems, or cross-team expectations
- The "what" isn't fully settled — building could go in several reasonable directions
- Multi-session scope where misaligned expectations would be costly to undo

**If OPEN and no active spec exists:**
Tell the user: *"This task looks open-ended — a spec would lock down the 'what' before we plan the 'how.' Want to run `/vibecheck:shape` to capture requirements first, or plan directly?"*

Wait for their answer before continuing:
- **Shape first:** run `/vibecheck:shape` with the task description, then return here once the spec exists
- **Plan directly:** proceed to Phase 2

**Skip this check if** a saved plan already exists (resume path), an active spec already exists (scope already defined), or `$ARGUMENTS` contained a plan-type override.

---

## Phase 2 — Discover and load plan skill(s)

Route to the right planning methodology using the suggested plan type from Phase 1.

Call `vibecheck_discover` to find matching specialists. **Use a short, action-focused query — the plan type, not the task description:**

```
vibecheck_discover(query="<plan-type>", layer="skill", skill_type="plan", limit=4)
```

Examples of good queries: `"feature-plan"`, `"debug-plan"`, `"design-plan"`. Do NOT include the objective title or task description in the query — domain-specific terms dilute relevance and cause mismatches.

**For each skill you decide to use, call `vibecheck_get_context(id)` to load its full brief.** The brief defines the specialist methodology — follow it exactly. Do not substitute your general knowledge for the skill's specific approach.

**How many specialists to select:**

- **Default: one.** Planning requires focus — running three specialists simultaneously produces an incoherent plan. Pick the specialist that matches the primary concern of the task.
- **Two specialists: only when the task genuinely spans two clearly distinct domains** with no overlap. Example: a task that requires *both* a DB migration *and* a new frontend panel. In that case, run both specialists sequentially — first the backend specialist (architecture-plan), then the frontend specialist (design-plan) — and produce one combined structured plan. Do not run two specialists for the same concern (e.g., feature-plan + architecture-plan both cover backend features).
- **Never three or more.** If the task seems to require three specialists, the scope is too large for one plan — split it.

**Override:** if `$ARGUMENTS` contains a plan type (e.g., `/vibecheck:plan architecture`), use that type regardless of what discover returns.

**Fallback — always load SKL-178, never drop to built-in:** If `vibecheck_discover` returns no results, returns results with no `skill_type=plan` match, or returns only unrelated skills, explicitly load `SKL-178` (feature-plan) as the default:

```
vibecheck_get_context("SKL-178")
```

Do not fall through to the Built-in Methodologies section. SKL-178 is the floor. Built-in prose is only used if VibeCheck is completely unreachable.

---

## Phase 3 — Generate planning brief and enter plan mode

### Generating the planning brief

**The specialist's job is to set up the planning session, not write the plan.**

Run the specialist methodology from Phase 2. Instead of producing a finished structured plan, produce a **planning brief** in this format:

> **Note:** Ignore the specialist skill's output format section — the skill informs the brief's Context and Approach, but the output format below replaces it entirely.

```markdown
## Planning Brief: <title>

**Type:** <plan-type> | **Spec:** <SPEC-id if available>

### Context
What we're building and why. Key background the plan should account for.

### Approach
Recommended planning direction — where to start, what to sequence first.

### Key questions to resolve in this plan
- [question the plan needs to answer]

### Risks to address
- [risk the plan should mitigate or call out]

### Files in scope
- [relevant files from Phase 1]
```

**If a saved plan was found** and the user wants to resume: load it with `vibecheck_get_context`, summarise the remaining steps, and call `EnterPlanMode` with the remaining steps as content.

### Entering plan mode

Call `EnterPlanMode` with the planning brief as the scaffolding content. The user generates the implementation plan interactively in plan mode.

### Post-approval: save and exit

When the user approves the plan, **before calling ExitPlanMode**:

**Extract structured fields from the approved plan.** The user built the plan interactively in plan mode — parse their approved plan text to populate the payload fields below. Extract steps as an ordered array, pull out any acceptance criteria and risks, and identify out-of-scope items. If a field isn't present in the plan text, omit it or pass an empty array.

1. **Extract the plan title** from the plan's first `##` heading (e.g., `## Plan: Self-Improvement Loop v2` → title is `"Plan: Self-Improvement Loop v2"`). This is the canonical title — do NOT use the Claude Code plan filename (e.g., "valiant-enchanting-globe") as the title.

2. Save to the Context Library:

```
vibecheck_create_context(
    type="plan",
    title="<title from the plan's first ## heading>",
    context_summary="<one sentence: what this plan is for>",
    tags=["plan", "<plan-type>"],
    brief=<full plan markdown>,
    predecessor_id=<active_spec_id or objective_id if available>
)
```

3. Report the plan label to the user: **"Plan saved as PLN-XX."** Include the Claude Code plan file reference for cross-referencing (e.g., "Claude Code plan ref: valiant-enchanting-globe").

4. Call `ExitPlanMode`.

**If VibeCheck is unreachable**, skip the save, note to the user that the plan was not persisted, and still call `ExitPlanMode`.

> **Title rule:** The plan title must come from the plan content (the first `##` heading), never from the Claude Code plan filename. The filename is a random slug (e.g., "valiant-enchanting-globe") used internally by Claude Code — it is not meaningful to the user.

### Resolve on completion

After the implementation of this plan is complete, call `vibecheck_resolve` on both the spec ID (if active) and the plan ID (PLN-*).

---

## Built-in Methodologies (fallback when no skill is loaded)

> **Note:** These describe the methodology to gather context — use them to inform the planning brief's Context, Approach, and Risks sections. Do NOT produce a full plan from them; output only the planning brief format defined in Phase 3 above.

### feature-plan
Start from acceptance criteria → identify data model changes → list API/service layer changes → list UI changes → identify integration points and risks → draft 4–6 ordered steps.

### debug-plan
Frame the hypothesis → identify reproduction steps → list diagnostic checkpoints → prioritize by likelihood → draft investigation steps. Find the cause first; fix steps come after.

### architecture-plan
Map current state → identify proposed change → assess blast radius (what breaks, what must migrate) → sequence changes to minimize breakage → flag rollback strategy.

### design-plan
Identify user-facing goal → list affected components → describe visual/interaction intent → identify reuse opportunities → sequence from layout to detail.

### refactor-plan
Clarify refactor goal → identify what must NOT change (public contracts, test coverage) → sequence changes to keep tests green throughout → define the done signal.

### product-plan
Frame the problem → define the user outcome → write 3 acceptance criteria (success from the user's POV) → identify the smallest shippable version → list what's out of scope.
