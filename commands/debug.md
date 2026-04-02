---
description: Debug phase guidance — routes to diagnostic methodology skills for structured root-cause analysis
allowed-tools: Bash, Read, Grep, Glob
---

You will provide debug-phase guidance for the current issue, routing to specialized debug skills for diagnostic methodology.

**Your job is: find the root cause before writing any fix code.**

---

## Phase 1 — Gather context

Understand what is broken:
- What error or unexpected behavior is occurring
- When it started
- What changed recently

---

## Phase 2 — Discover and load debug skills

```
vibecheck_discover(query="debug root cause diagnostic methodology", layer="skill", skill_type="debug", situation="Debug phase — investigating failure", limit=4)
```

For each matched skill, call `vibecheck_get(id)` to load the full brief. The brief defines the methodology — follow it exactly.

If no skills are found, use the built-in debug guidance below.

---

## Phase 3 — Execute debug methodology

For each loaded debug specialist, follow its methodology in full.

### Built-in Debug Guidance (fallback when no skill is loaded)

1. **Observe and reproduce.** Write down the exact error, inputs, and conditions before forming any hypothesis.
2. **Hypothesize before touching code.** List at least 3 candidate root causes. Define a falsifiable test for each.
3. **One variable per experiment.** Two simultaneous changes mean you cannot know which mattered.
4. **No speculative fixes.** If you are not sure what is wrong, you are still investigating, not fixing.
5. **Add a regression test.** Write the test first, watch it fail, then apply the fix.
