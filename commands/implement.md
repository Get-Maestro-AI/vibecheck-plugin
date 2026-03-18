---
description: Begin implementing a spec from the Context Library (e.g. /vibecheck:implement SPEC-4)
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

Begin implementing **$ARGUMENTS** from the VibeCheck Context Library.

---

## Phase 0 — Route by argument type

Inspect `$ARGUMENTS` and take one of three paths:

**PLN-* (plan ID):**
- Call `vibecheck_get_context(id="$ARGUMENTS")` to load the plan
- Skip directly to **Step 3 — Explore the codebase** below
- The plan already defines the steps — do not re-plan

**SPEC-* (spec ID):**
- Call `vibecheck_implement(id="$ARGUMENTS")` to load the spec brief
- Then check for an existing plan — see **Step 1** below

**No argument or unrecognized format:**
- Ask the user to provide a SPEC-* or PLN-* ID before proceeding

---

## Instructions

You are now in **implementation mode**.

**Step 1 — Understand the spec**
Read the spec brief completely (already loaded via `vibecheck_implement`). Note:
- What the spec asks for (the "what")
- Any constraints or standards that apply (the "how")
- What done looks like (the acceptance criteria, if present)

**Step 2 — Check for an existing plan**
Look up any active plan linked to this spec:

```bash
_VC_CONF="$HOME/.config/vibecheck/config"
_VC_KEY="${VIBECHECK_API_KEY:-$(grep '^api_key=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"
_AUTH_ARGS=()
[ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY")

curl -s "$_VC_URL/api/plans?spec_id=$ARGUMENTS&status=active" "${_AUTH_ARGS[@]}" | python3 -m json.tool
```

**If a plan is found:**
- Load it with `vibecheck_get_context(id=<plan_id>)`
- Verify it is still aligned with the spec:
  - Does the plan goal match the spec's objective?
  - Are the steps consistent with the spec's scope?
- If aligned: proceed directly to **Step 3 — Implement**
- If misaligned or stale: surface the mismatch to the user and offer to re-plan via `/vibecheck:plan` or proceed with the spec directly

**If no plan is found:**
Classify the task scope before deciding how to proceed:

**BOUNDED** (scope fully defined, single session, no open design questions):
- Proceed directly to **Step 3 — Implement** — a formal plan adds little value here

**OPEN** (multi-file changes, unresolved design decisions, or multi-session scope):
- Tell the user: *"No active plan found for this spec. This looks like it could benefit from a planning step before diving in. Want to run `/vibecheck:plan` first, or implement directly?"*
- Wait for their answer:
  - **Plan first:** run `/vibecheck:plan $ARGUMENTS`, then proceed to **Step 3** once the plan is approved
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
2. Run `/vibecheck:review` to review changes before committing
