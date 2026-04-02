---
description: Reflect phase — session retrospective, skill refinement, and learning loop
allowed-tools: Bash, Read, Grep, Glob
---

You will run the reflect phase, which captures session learnings, refines skills, and closes the learning loop.

**Your job is: capture what matters before context is lost, and improve the system for next time.**

---

## Phase 1 — Discover and load reflect specialists

```
vibecheck_discover(query="reflect retrospective skill refinement session learnings", layer="skill", skill_type="reflect", limit=4)
```

For each matched skill, call `vibecheck_get(id)` to load the full brief. The brief defines the methodology — follow it exactly.

**Important:** This is a manual invocation. Tell each specialist to **skip the session dedup check** — explicit user intent always runs.

If no skills are found, fall back to the built-in reflect criteria below.

---

## Phase 2 — Run reflect specialists

For each loaded reflect specialist, follow its methodology in full. The specialist scans for friction signals and captures session learnings as needed.

### Built-in Reflect Criteria (fallback when no skill is loaded)

1. **What changed?** List files modified and what each one now does differently. One sentence per file.
2. **What was decided?** List architectural or design decisions made this session. For each: what, why, and what depends on it.
3. **What was discovered?** Problems, constraints, or facts about the codebase that weren't known before.
4. **What's incomplete?** What was intentionally deferred? What should the next session start with?
5. **Skill friction?** Did any skill fire incorrectly, miss the context, or produce unhelpful guidance? If so, refine it.

Create decision contexts for significant architectural choices. File issues for discovered problems. Save the retrospective as a note.
