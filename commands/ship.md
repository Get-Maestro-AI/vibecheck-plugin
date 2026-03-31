---
description: Ship phase guidance — routes to shipping workflow skills for PR prep, commit, and release
allowed-tools: Bash, Read, Grep, Glob
---

You will provide ship-phase guidance for getting the current work committed and pushed, routing to specialized ship skills.

**Your job is: clean execution — get the changes committed and pushed without introducing new problems.**

---

## Phase 1 — Gather context

Check the current state of the working tree:
- What files are staged and unstaged
- What branch you're on
- Whether tests pass

---

## Phase 2 — Discover and load ship skills

```
vibecheck_discover(query="ship commit push PR release workflow", layer="skill", skill_type="ship", situation="Ship phase — preparing to commit and push", limit=4)
```

For each matched skill, call `vibecheck_get_context(id)` to load the full brief. The brief defines the methodology — follow it exactly.

If no skills are found, use the built-in ship guidance below.

---

## Phase 3 — Execute ship methodology

For each loaded ship specialist, follow its methodology in full.

### Built-in Ship Guidance (fallback when no skill is loaded)

1. **Sync with main.** `git fetch origin && git rebase origin/main`. Resolve conflicts before proceeding.
2. **Final check.** `git diff --stat HEAD` — confirm changed files match intent. No stray files, no debug artifacts.
3. **Run fast tests.** Unit tests, lint, type check. If anything fails, fix it before committing.
4. **Write a good commit message.** Explain *why*, not *what*. The diff shows what changed.
5. **Stage intentionally.** Use `git add -p` or add specific files — never `git add .`.
6. **Push and open PR** if on a branch. Link to relevant context IDs (SPEC-X, PLN-X).
