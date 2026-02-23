---
name: checkpoint
description: >-
  Guides Claude Code agents on when and how to call VibeCheck MCP tools.
  Use when transitioning between work phases (planning, implementing, reviewing, done),
  reporting completed subtasks, flagging uncertainty, or requesting developer guidance.
allowed-tools: Read
---

# VibeCheck Push Protocol

## Non-negotiable rules

- ALWAYS include `files_modified` in every `vibecheck_report_progress` call
- ALWAYS call `vibecheck_checkpoint` with `status_label: "reviewing"` before final completion
- Completion is a hard precondition, not optional:
  - DO NOT treat an objective as done until completion protocol succeeds
  - Preferred path: run `/vibecheck:complete` (single command)
  - Fallback path: `vibecheck_begin_completion` -> `/vibecheck:review` -> `vibecheck_finalize_objective`
- If completion is blocked, resolve the blocker and retry (with explicit `objective_id` when available)

---

## When to call each tool

### `vibecheck_checkpoint` — call at phase transitions

- After planning is complete, before implementation starts: `status_label: "implementing"`
- After implementation is complete, before testing/review: `status_label: "reviewing"`
- When you have finished all work:
  1) run `/vibecheck:complete`
  2) only after success, call `status_label: "done"`
- When you discover you need to debug something unexpected: `status_label: "debugging"`

**When transitioning to `"reviewing"`: launch a targeted background code review subagent.**

See [references/reviewing-procedure.md](references/reviewing-procedure.md) for the full 4-step procedure.

### `vibecheck_report_progress` — call after meaningful subtasks

- After completing a non-trivial function, component, or module
- After all tests pass for a specific feature
- After resolving a specific bug

### `vibecheck_begin_completion` — call when objective is ready for final review

- Use after implementation/testing is done and before `/vibecheck:review`
- If blocked with "No active objective", retry with explicit `objective_id` from the dashboard/UI context

### `vibecheck_finalize_objective` — call after review payload is submitted

- If blocked with `protocol_status=pending_protocol`, run `/vibecheck:review` first
- Treat blocked finalize as actionable state, not an error

### `/vibecheck:complete` — preferred completion path

- Use this as the default completion workflow
- It runs begin -> review payload -> finalize in one flow
- If blocked, surface the blocker and retry with explicit `objective_id`

**`files_modified` is required, not optional.** List every file you edited in this subtask. This list scopes automated reviews — underreporting means issues get missed. Include files modified via Bash (e.g., `sed` rewrites) that don't appear as Edit/Write tool calls.

**Writing good `completed_subtasks`**: describe what was *accomplished* and *why it matters*, not which file was edited. The dashboard shows these directly.
- Bad: `"Edited code_quality_review.py"`, `"Updated state.py"`
- Good: `"Added confidence score filtering — findings below threshold 7 are suppressed"`, `"Collapsed duplicate step events in record_event() using updated_at dedup"`

**Writing a good `current_task`**: one sentence, active voice, problem-focused.
- Bad: `"Working on the detector"`, `"Fixing stuff"`
- Good: `"Reducing false positives in CodeQualityReviewDetector by adding confidence scores"`

### `vibecheck_flag_uncertainty` — call BEFORE proceeding when uncertain

- When you're about to make an irreversible change and aren't sure which approach is right
- When the requirements could be interpreted multiple ways and the choice matters
- When you've identified a significant risk that the developer should know about

### `vibecheck_request_guidance` — call when blocked on a human decision

- When you need a decision that only the developer can make
- When the task requires credentials, access, or external information you don't have
- When you discover the task conflicts with existing code in a way that requires prioritization

---

## What NOT to do

- Do not call these tools obsessively on every step — *do* call at the natural breakpoints listed above, once per phase transition
- Do not skip `vibecheck_flag_uncertainty` when genuinely uncertain — *do* call it immediately; the cost of a wrong assumption is higher than the cost of the tool call
- Do not call `vibecheck_checkpoint("done")` until the work is actually complete and tested — *do* call it as soon as you have verified the work is done
