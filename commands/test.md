---
description: Test phase guidance — routes to test strategy skills for coverage planning and test generation
allowed-tools: Bash, Read, Grep, Glob
---

You will provide test-phase guidance for the current work, routing to specialized test skills for strategy and coverage.

**Your job is: determine what to test, at what level, and which edge cases matter most.**

---

## Phase 1 — Gather context

Understand what changed:
- What code was modified or added
- What behaviors are new or changed
- What contracts (API responses, function signatures) are affected

---

## Phase 2 — Discover and load test skills

```
vibecheck_discover(query="test strategy coverage edge cases", layer="skill", skill_type="test", situation="Test phase — planning test coverage for recent changes", limit=4)
```

For each matched skill, call `vibecheck_get(id)` to load the full brief. The brief defines the methodology — follow it exactly.

If no skills are found, use the built-in test guidance below.

---

## Phase 3 — Execute test methodology

For each loaded test specialist, follow its methodology in full.

### Built-in Test Guidance (fallback when no skill is loaded)

1. **Test behavior, not implementation.** Tests that assert on observable behavior survive refactors.
2. **Choose the right level.** Unit for pure logic, integration for API/DB boundaries, E2E only for critical paths.
3. **Map test cases systematically.** For each changed behavior: happy path, boundary cases, error cases, interaction cases.
4. **Prioritize by risk.** Acceptance criteria first, then highest-risk edge cases, then regression tests.
5. **Name tests as specifications.** `test_returns_404_when_user_not_found` not `test_error`.
