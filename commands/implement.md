---
description: Begin implementing a spec from the Context Library (e.g. /vibecheck:implement SPEC-4)
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

Begin implementing spec **$ARGUMENTS** from the VibeCheck Context Library.

## Load the spec

Call `vibecheck_implement` with the spec ID:

```
vibecheck_implement(id="$ARGUMENTS")
```

This will return the full implementation brief: the spec description, related past decisions, and standing standards that apply. Read everything before writing a single line of code.

---

## Instructions

You are now in **implementation mode** for this spec.

**Step 1 — Understand before building**
Read the spec brief completely. Note:
- What the spec asks for (the "what")
- Any constraints or standards that apply (the "how")
- What done looks like (the acceptance criteria, if present)

**Step 2 — Explore the existing codebase**
Use Grep, Glob, and Read to understand what already exists. Identify:
- Files and modules that will be affected
- Patterns already in use that the implementation should follow
- Anything in the spec brief that needs clarification before proceeding

**Step 3 — Plan before coding**
Write out a numbered implementation plan. For each step:
- Which file(s) are changing and why
- What the change is
- Any risks or edge cases to handle

Share the plan before starting. If anything is unclear or the scope is larger than expected, surface that now.

**Step 4 — Implement**
Execute the plan step by step. Call `vibecheck_update` at each phase transition (planning → implementing → reviewing).

**Step 5 — Complete**
When implementation is done:
1. Call `vibecheck_resolve` with the spec ID to mark it implemented
2. Run `/vibecheck:review` to review changes before committing
