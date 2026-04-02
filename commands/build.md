---
description: Build phase guidance — implement a spec or run build methodology (e.g. /vibe:build SPEC-4)
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

Begin implementing **$ARGUMENTS** or provide build-phase guidance for the current task.

---

## Phase 0 — Route by argument

Inspect `$ARGUMENTS` and take one of three paths:

**PLN-* (plan ID):**
- Call `vibecheck_get(id="$ARGUMENTS")` to load the plan
- Skip directly to **Step 3 — Explore the codebase** below
- The plan already defines the steps — do not re-plan

**SPEC-* (spec ID):**
- Call `vibecheck_implement(id="$ARGUMENTS")` to load the spec brief
- Then check for an existing plan — see **Step 1** below

**No argument:**
- Proceed to **Phase 1 — Gather context** below

---

## Phase 1 — Gather context

Read the active plan or spec if one exists:

```
vibecheck_get_active_context_set()
```

If no active context set, check for recent session context:
- What files have been modified
- What the current task is
- What phase the work is in

---

## Phase 2 — Discover and load build skills

```
vibecheck_discover(query="build implementation methodology coding", layer="skill", skill_type="build", situation="Build phase — implementing current task", limit=4)
```

For each matched skill, call `vibecheck_get(id)` to load the full brief. The brief defines the methodology — follow it exactly.

If no skills are found, use the built-in build guidance below.

---

## Phase 3 — Execute build methodology

For each loaded build specialist, follow its methodology in full.

### Built-in Build Guidance (fallback when no skill is loaded)

1. **Read the plan/spec first.** Do not start coding until you understand the acceptance criteria.
2. **One step at a time.** Complete and verify each plan step before starting the next.
3. **No drive-by improvements.** If you notice something worth fixing that is not in the plan, file it as an issue.
4. **Verify after each step.** Each step should leave the system in a valid, testable state.
5. **Stay in scope.** Check `git diff --stat` periodically — only files in scope should be changing.

---

## Implementation Flow (for SPEC-*/PLN-* arguments)

**Step 1 — Understand the spec**
Read the spec brief completely (already loaded via `vibecheck_implement`). Note:
- What the spec asks for (the "what")
- Any constraints or standards that apply (the "how")
- What done looks like (the acceptance criteria, if present)

**Step 2 — Check for an existing plan**
Look up any active plan linked to this spec:

```
vibecheck_discover(query="plan for $ARGUMENTS", layer="work", type="plan", limit=3)
```

**If a plan is found:**
- Load it with `vibecheck_get(id=<plan_id>)`
- Verify it is still aligned with the spec:
  - Does the plan goal match the spec's objective?
  - Are the steps consistent with the spec's scope?
- If aligned: proceed to **Step 3**
- If misaligned or stale: surface the mismatch and offer to re-plan via `/vibe:plan` or proceed directly

**If no plan is found:**
Classify the task scope before deciding how to proceed:

**BOUNDED** (scope fully defined, single session, no open design questions):
- Proceed to **Step 3** — a formal plan adds little value here

**OPEN** (multi-file changes, unresolved design decisions, or multi-session scope):
- Tell the user: *"No active plan found for this spec. This looks like it could benefit from a planning step before diving in. Want to run `/vibe:plan` first, or implement directly?"*
- Wait for their answer:
  - **Plan first:** run `/vibe:plan $ARGUMENTS`, then proceed to **Step 3** once the plan is approved
  - **Implement directly:** proceed to **Step 3** without a plan

**Step 3 — Explore the codebase**
Use Grep, Glob, and Read to understand what already exists. Identify:
- Files and modules that will be affected
- Patterns already in use that the implementation should follow
- Anything in the plan or spec brief that needs clarification before proceeding

**Step 4 — Implement**
Execute the plan step by step, in order. For each step:
- Check it off mentally as done before moving to the next
- Call `vibecheck_update` at each phase transition (implementing → reviewing)

**Step 5 — Complete**
When implementation is done:
1. Call `vibecheck_resolve` with the spec ID to mark it implemented
2. If a PLN-* plan was used, call `vibecheck_resolve` with the plan ID to mark it complete
3. Run `/vibe:review` to review changes before committing
