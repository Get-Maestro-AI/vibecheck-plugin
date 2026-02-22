# VibeCheck Push Protocol

Use the VibeCheck MCP tools to report your state at natural breakpoints during work. This enables real-time dashboard updates and quality signal generation.

## When to call each tool

### `vibecheck_checkpoint` — call at phase transitions
- After planning is complete, before implementation starts: `status_label: "implementing"`
- After implementation is complete, before testing/review: `status_label: "reviewing"`
- When you have finished all work: `status_label: "done"`
- When you discover you need to debug something unexpected: `status_label: "debugging"`

### `vibecheck_report_progress` — call after meaningful subtasks
- After completing a non-trivial function, component, or module
- After all tests pass for a specific feature
- After resolving a specific bug

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

## What NOT to do
- Do not call these tools obsessively on every step — use them at natural breakpoints
- Do not skip `vibecheck_flag_uncertainty` when you're genuinely uncertain — the cost of a wrong assumption is higher than the cost of the tool call
- Do not call `vibecheck_checkpoint("done")` until the work is actually complete and tested

## Failure modes reference
See `failure-modes-reference.md` for the specific patterns VibeCheck detects and what triggers them.
