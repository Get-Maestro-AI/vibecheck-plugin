---
description: Create a new context in the VibeCheck Context Library (note, spec, decision, plan)
allowed-tools: ""
---

Create a new context in the VibeCheck Context Library.

**User input:** $ARGUMENTS

## Instructions

Parse the user's input to determine the context type and title.

**Parsing rules:**
1. If the input starts with a known type followed by a colon (`decision:`, `spec:`, `note:`, `research:`, `standard:`), use that as the `type` and the rest as the title. Otherwise default to `note`.
2. If the input contains a `|` separator, treat the part before `|` as the title and the part after as the `brief`.
3. If no `|` separator, use the full input as the title.
4. If the input contains `#tag` patterns, extract them as tags.

**Note:** Issues are first-class board Items, not contexts. Use `/vibe:issue <title>` to file an issue.

Call `vibecheck_create` with the parsed fields:
- `title` (required)
- `type` (default: `note`)
- `brief` (if provided after `|`)
- `tags` (if `#tag` patterns present)

After creation, report:
- The assigned label and UUID
- The type and title
- Next steps: `/vibe:context <label>` to view, `/vibe:shape <label>` to develop further, `/vibe:implement <label>` if it's a spec

**Examples:**
- `/vibe:create Add caching layer for embeddings`
- `/vibe:create decision: Switch from SQLite to PostgreSQL | Performance requirements exceed SQLite capabilities`
- `/vibe:create spec: Rate limiting for the summarizer endpoint | Prevent abuse and control LLM costs #backend #cost`
