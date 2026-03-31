---
description: Build phase guidance — routes to implementation skills for coding methodology and conventions
allowed-tools: Bash, Read, Grep, Glob
---

You will provide build-phase guidance for the current implementation task, routing to specialized build skills for methodology.

**Your job is: help the developer implement effectively — aligned with specs, plans, and team conventions.**

---

## Phase 1 — Gather context

Read the active plan or spec if one exists. Understand what is being built and what the acceptance criteria are.

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

For each matched skill, call `vibecheck_get_context(id)` to load the full brief. The brief defines the methodology — follow it exactly.

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
