---
description: Browse contexts in the VibeCheck Context Library with optional filters
allowed-tools: ""
---

List contexts from the VibeCheck Context Library.

**Arguments:** $ARGUMENTS

## Instructions

Call the `vibecheck_list` MCP tool to fetch contexts. Parse the arguments above to determine filters:

- If arguments contain a type keyword (`research`, `spec`, `issue`, `decision`, `note`, `standard`), pass it as the `type` filter
- If arguments contain a status keyword (`draft`, `shaped`, `ready`, `dispatched`, `implemented`, `active`, `archived`, `open`), pass it as the `status` filter
- If arguments contain `tag:something`, pass `something` as the `tag` filter
- If arguments are empty, list all contexts (no filters)

Present the results as a compact table:

| Label | Type | Status | Title |
|-------|------|--------|-------|
| ISS-12 | issue | open | Missing slash commands for context system |

If no results are found, say so and suggest trying different filters.

**Examples:**
- `/vibe:contexts` — list all contexts
- `/vibe:contexts issue` — list issues
- `/vibe:contexts issue open` — list open issues
- `/vibe:contexts spec ready` — list specs that are ready for implementation
- `/vibe:contexts tag:severity:high` — list contexts with a specific tag
