---
description: Search for semantically related contexts by free-text query
allowed-tools: ""
---

Search the VibeCheck Context Library for contexts related to your query.

**Query:** $ARGUMENTS

## Instructions

Call the `vibecheck_find_related` MCP tool with the query provided above.

- Pass the full argument text as the `query` parameter
- If the query mentions "standards" or "rules", set `layer` to `"standard"`
- If the query mentions "decisions", set `layer` to `"decision"`
- Otherwise omit `layer` to search all

Present results as a compact list, ordered by relevance:

1. **Title** (label) — *type, status*
   > First ~100 chars of the brief...

If no results are found, say so and suggest:
- Trying different keywords
- Using `/vibecheck:contexts` to browse all contexts
- Using `/vibecheck:create` to capture a new one

**Examples:**
- `/vibecheck:search how do we handle authentication`
- `/vibecheck:search session embedding strategy`
- `/vibecheck:search coding standards for error handling`
