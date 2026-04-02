---
description: Create a new issue Item in VibeCheck (ISS-X label, tracked on the board)
allowed-tools: ""
---

Create a new issue in the VibeCheck board.

**User input:** $ARGUMENTS

## Instructions

Parse the user's input:

1. If the input contains a `|` separator, treat the part before `|` as the title and the part after as the brief.
2. If no `|`, use the full input as the title.
3. If the input contains `#tag` patterns, extract them as tags.

Call `vibecheck_create` with:
- `type`: `"issue"` (always)
- `title` (required)
- `brief` (if provided after `|`)
- `tags` (if `#tag` patterns present)

The MCP server routes `type='issue'` transparently to the Items API — the result will have an `ISS-X` label.

After creation, report:
- The assigned `ISS-X` label
- The title
- Next steps: `/vibe:fix <label>` to investigate and fix it, `/vibe:context <label>` to view full detail

**Examples:**
- `/vibe:issue Session titles missing for forked sessions`
- `/vibe:issue vibe:create crashes when server is offline | Happens when the VibeCheck server is not running`
- `/vibe:issue Drawer doesn't close on Escape key #ux #frontend`
