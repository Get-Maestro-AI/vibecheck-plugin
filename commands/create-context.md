---
description: Create a new context in the VibeCheck Context Library
allowed-tools: ""
---

Create a new context in the VibeCheck Context Library.

**User input:** $ARGUMENTS

## Instructions

Parse the user's input to create a context. The input may be:
- A simple title: `/vibecheck:create-context Add rate limiting to API`
- A title with type prefix: `/vibecheck:create-context decision: Use PostgreSQL for session storage`
- A title with description: `/vibecheck:create-context Add rate limiting to API | We need to prevent abuse of the summarizer endpoint`

**Parsing rules:**
1. If the input starts with a known type followed by a colon (`decision:`, `issue:`, `spec:`, `note:`, `research:`, `standard:`), use that as the `type` and the rest as the title. Otherwise default to `note`.
2. If the input contains a `|` separator, treat the part before as the title and the part after as the `brief`.
3. If no `|` separator is present, use the full input as the title.

Call `vibecheck_create_context` with the parsed fields:
- `title` (required)
- `type` (default: `note`)
- `brief` (if provided)
- `tags` (if the user included `#tag` patterns)

After creation, report back:
- The assigned label and ID
- The type and title
- A reminder that they can use `/vibecheck:context <label>` to view it or `/vibecheck:shape <label>` to develop it further

**Examples:**
- `/vibecheck:create-context Add caching layer for embeddings`
- `/vibecheck:create-context decision: Switch from SQLite to PostgreSQL | Performance requirements exceed SQLite capabilities`
- `/vibecheck:create-context issue: Session titles missing for forked sessions`
