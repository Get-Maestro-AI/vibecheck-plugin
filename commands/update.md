---
description: Post a progress checkpoint to the VibeCheck dashboard
---

Submit a `vibecheck_update` status checkpoint for the current project.

Arguments:
- `$ARGUMENTS` must be JSON with:
  - required: `status_label`, `summary`
  - optional: `current_task`, `completed_subtasks`, `files_modified`, `confidence`, `next_step`

Example:
`/vibecheck:update {"status_label":"implementing","summary":"Implemented completion protocol hardening.","current_task":"Cleaning objective resolution fallbacks","completed_subtasks":["Added robust fallback rules"],"files_modified":["vibecheck/event_processor.py"]}`

## Steps

1. Validate arguments:
   - If `$ARGUMENTS` is empty, explain usage and show the example above.
   - If JSON parsing fails, report "Invalid JSON" and show the expected shape.
   - If `status_label` or `summary` is missing, stop and report the missing field.

2. Parse the JSON from `$ARGUMENTS` and call the MCP tool with the extracted fields:

```
vibecheck_update(
  status_label="<status_label>",
  summary="<summary>",
  current_task="<current_task if provided>",
  completed_subtasks=["<subtask1>", ...],
  files_modified=["<file1>", ...],
  confidence="<confidence if provided>",
  next_step="<next_step if provided>"
)
```

3. Report outcome:
   - If the tool succeeds, confirm update posted.
   - If VibeCheck is unreachable, report that update was not saved.
   - If `status_label` is `"done"` and response indicates blocked completion, surface the reason and next action.

## Notes

- `status_label` must be one of: `planning`, `implementing`, `debugging`, `reviewing`, `done`
- Keep `summary` concise (1-2 sentences)
- Always include `files_modified` when files changed in this subtask
