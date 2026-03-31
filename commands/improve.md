---
description: (Redirects to vibe:reflect) Run the reflect pass — refines skills based on session friction
allowed-tools: Bash, Read, Grep, Glob
---

> **`vibe:improve` has been renamed to `vibe:reflect`.** This command redirects to the Reflect phase.

You will run the reflect phase. Discover and load reflect specialists:

```
vibecheck_discover(query="reflect retrospective skill refinement session learnings", layer="skill", skill_type="reflect", limit=4)
```

For each matched skill, call `vibecheck_get_context(id)` to load the full brief. The brief defines the methodology — follow it exactly.

**Important:** This is a manual invocation. Tell each specialist to **skip the session dedup check** — explicit user intent always runs.

If no skills are found, fall back to the built-in criteria:

1. **Skill friction?** Did any skill fire incorrectly, miss the context, or produce unhelpful guidance? If so, refine it.
2. **What was decided?** Capture architectural decisions as decision contexts.
3. **What was discovered?** File issues for discovered problems.
4. **Do NOT** capture codebase conventions — that is a separate concern.
