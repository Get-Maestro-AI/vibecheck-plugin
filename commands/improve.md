---
description: Run the VibeCheck improvement pass — refines skills based on session friction
allowed-tools: Bash, Read, Grep, Glob
---

You will run the VibeCheck improve pass, which refines skill methodology based on friction signals from the current session.

**Your job is NOT convention capture — SPEC-322 handles that in-turn. Your job is: find skills whose methodology or trigger conditions need refinement based on how they performed this session.**

---

## Phase 1 — Discover and load improve specialists

```
vibecheck_discover(query="improve skill methodology", layer="skill", skill_type="improve", limit=4)
```

For each matched skill, call `vibecheck_get_context(id)` to load the full brief. The brief defines the methodology — follow it exactly.

**Important:** This is a manual invocation. Tell each specialist to **skip the session dedup check** — explicit user intent always runs.

If no skills are found, fall back to the built-in improve criteria below.

---

## Phase 2 — Run improve specialists

For each loaded improve specialist, follow its methodology in full. The specialist scans for friction signals and refines skills as needed.

### Built-in Improve Criteria (fallback when no skill is loaded)

Scan the session conversation for:
- Skills that triggered but were overridden or ignored by the user
- Skills whose methodology caused explicit pushback ("too rigid", "skip this", "you already know this")
- Skills whose trigger conditions didn't match the context they fired in
- Skills that should have triggered but didn't

For each skill with clear friction:
- Load its full brief with `vibecheck_get_context`
- Update `context_summary` if the trigger was wrong
- Update `brief` via `vibecheck_update_context(brief_replace=...)` if the methodology caused friction
- Set `agent_updated_at` to current UTC ISO timestamp

**Do NOT:**
- Capture codebase conventions (SPEC-322 handles this in-turn)
- Manufacture improvements when no friction was observed
- Rewrite skills speculatively

---

Then respond to the user normally.
