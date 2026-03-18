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

Route to the right planning methodology. Use the suggested plan type and objective title from Phase 1 as your query.

Call `vibecheck_discover` to find matching specialists:

```
vibecheck_discover(query="plan <objective title or task description>", layer="skill", skill_type="plan", limit=4)
```

**For each skill you decide to use, call `vibecheck_get_context(id)` to load its full brief.** The brief defines the specialist methodology — follow it exactly. Do not substitute your general knowledge for the skill's specific approach.

**How many specialists to select:**

- **Default: one.** Planning requires focus — running three specialists simultaneously produces an incoherent plan. Pick the specialist that matches the primary concern of the task.
- **Two specialists: only when the task genuinely spans two clearly distinct domains** with no overlap. Example: a task that requires *both* a DB migration *and* a new frontend panel. In that case, run both specialists sequentially — first the backend specialist (architecture-plan), then the frontend specialist (design-plan) — and produce one combined structured plan. Do not run two specialists for the same concern (e.g., feature-plan + architecture-plan both cover backend features).
- **Never three or more.** If the task seems to require three specialists, the scope is too large for one plan — split it.

**Override:** if `$ARGUMENTS` contains a plan type (e.g., `/vibecheck:plan architecture`), use that type regardless of what discover returns.

If `vibecheck_discover` returns no results or no match is close, use the built-in methodology for the suggested plan type (see Built-in Methodologies below).

---

## Phase 3 — Execute plan, save, and enter plan mode

### Executing the plan

If a saved plan was found and the user wants to resume: load it, summarise remaining steps, and proceed directly to `EnterPlanMode` with the remaining steps highlighted.

Otherwise, run the specialist methodology (or built-in fallback) to produce a structured plan in this exact format:

```markdown
## Plan: <title>

**Type:** <plan-type> | **Skill:** <skill-name or "built-in"> | **Objective:** <objective title or ID>

### Goal
One sentence: what success looks like when this plan is complete.

### Steps
1. <step> — <why / what to watch for>
2. <step> — <why / what to watch for>
(3–8 steps maximum. Each step must be independently verifiable.)

### Risks & Unknowns
- <risk or unknown that could derail this plan>

### Acceptance Criteria
- [ ] <concrete, testable condition>

### Out of Scope
- <what we are explicitly NOT doing in this plan>
```

### Save the plan to VibeCheck

After generating the plan, POST it to VibeCheck:

```bash
_VC_CONF="$HOME/.config/vibecheck/config"
_VC_KEY="${VIBECHECK_API_KEY:-$(grep '^api_key=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"
_AUTH_ARGS=()
[ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY")

curl -s -X POST "$_VC_URL/api/push/vc-plan" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d '<YOUR_JSON_PAYLOAD>'
```

JSON payload structure:
```json
{
  "session_id": "!`echo ${CLAUDE_SESSION_ID:-unknown}`",
  "cwd": "!`pwd`",
  "objective_id": "<objective_id from Phase 1, or empty>",
  "spec_id": "<active_spec_id from Phase 1, or empty>",
  "plan_type": "<plan-type>",
  "skill_id": "<skill context ID if one was loaded, or empty>",
  "title": "<plan title>",
  "steps": [
    { "order": 1, "description": "<step>", "done": false },
    { "order": 2, "description": "<step>", "done": false }
  ],
  "risks": ["<risk>"],
  "acceptance_criteria": ["<criterion>"],
  "out_of_scope": ["<item>"]
}
```

### Save to the Context Library

After POSTing to `/api/push/vc-plan`, also write the plan to the Context Library:

```
vibecheck_create_context(
    type="plan",
    title="Plan: <objective title> (<today's date>)",
    context_summary="<one sentence: what this plan is for>",
    tags=["plan", "<plan-type>"],
    brief=<full plan markdown>,
    predecessor_id=<active_spec_id or objective_id if available>
)
```

### Enter plan mode

Finally, call `EnterPlanMode` with the structured plan as the content for user review and approval. The user will review the plan and either approve it (proceeding to implementation) or request changes.

**If VibeCheck is unreachable**, present the plan to the user and proceed to `EnterPlanMode` without saving — note that the plan was not persisted.

---

## Built-in Methodologies (fallback when no skill is loaded)

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
