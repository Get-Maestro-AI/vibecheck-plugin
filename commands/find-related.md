---
description: Search for semantically related contexts by free-text query
allowed-tools: ""
---

Find contexts semantically related to a query.

**Query:** $ARGUMENTS

## Instructions

Call the `vibecheck_find_related` MCP tool with the query provided above.

- Pass the full argument text as the `query` parameter
- If the query mentions "standards" or "rules", set `layer` to `"standard"`
- If the query mentions "decisions", set `layer` to `"decision"`
- Otherwise, omit the `layer` parameter to search all

Present the results as a compact list, ordered by relevance:

1. **Title** (label) — *type, status*
   > First ~100 chars of the brief...

2. **Title** (label) — *type, status*
   > First ~100 chars of the brief...

If no results are found, say so and suggest:
- Trying different keywords
- Using `/vibecheck:contexts` to browse all contexts
- Using `/vibecheck:create-context` to capture a new one

**Examples:**
- `/vibecheck:find-related how do we handle authentication`
- `/vibecheck:find-related session embedding strategy`
- `/vibecheck:find-related coding standards for error handling`
