---
name: checkpoint
description: >-
  Guides Claude Code agents on when and how to call VibeCheck MCP tools.
  Use when transitioning between work phases (planning, implementing, reviewing, done),
  and reporting completed subtasks.
allowed-tools: Read
---

# VibeCheck Push Protocol

## Non-negotiable rules

- ALWAYS include `files_modified` in every `vibecheck_update` call where files changed
- ALWAYS send `vibecheck_update` with `status_label: "reviewing"` before final completion
- After substantial work, run `/vibecheck:review` to catch issues before committing
- After review is clean, send `vibecheck_update` with `status_label: "done"`

---

## When to call each tool

### `vibecheck_update` — unified checkpoint updates (with progress details)

- Include `status_label` and `summary` on every call (required)
- Include progress details when useful: `current_task`, `completed_subtasks`, `files_modified`, `next_step`
- After planning is complete, before implementation starts: `status_label: "implementing"`
- After implementation is complete, before testing/review: `status_label: "reviewing"`
- When you have finished all work and review is clean: `status_label: "done"`
- When you discover you need to debug something unexpected: `status_label: "debugging"`

**When transitioning to `"reviewing"`: launch a targeted background code review subagent.**

See [references/reviewing-procedure.md](references/reviewing-procedure.md) for the full 4-step procedure.

**`files_modified` is required, not optional.** List every file you edited in this subtask when sending `vibecheck_update`. This list scopes automated reviews — underreporting means issues get missed. Include files modified via Bash (e.g., `sed` rewrites) that don't appear as Edit/Write tool calls.

**Writing good `completed_subtasks`**: describe what was *accomplished* and *why it matters*, not which file was edited. The dashboard shows these directly.
- Bad: `"Edited code_quality_review.py"`, `"Updated state.py"`
- Good: `"Added confidence score filtering — findings below threshold 7 are suppressed"`, `"Collapsed duplicate step events in record_event() using updated_at dedup"`

**Writing a good `current_task`**: one sentence, active voice, problem-focused.
- Bad: `"Working on the detector"`, `"Fixing stuff"`
- Good: `"Reducing false positives in CodeQualityReviewDetector by adding confidence scores"`

## What NOT to do

- Do not call these tools obsessively on every step — *do* call at the natural breakpoints listed above, once per phase transition
- Do not send a `vibecheck_update` checkpoint with `status_label: "done"` until the work is actually complete and tested — *do* send it as soon as you have verified the work is done
