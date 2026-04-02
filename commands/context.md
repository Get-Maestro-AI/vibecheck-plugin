---
description: View full detail for a context by ID or label (e.g. ISS-12, DEC-3)
allowed-tools: ""
---

Show the full detail for a VibeCheck context.

**Context identifier:** $ARGUMENTS

## Instructions

Call the `vibecheck_get` MCP tool with the identifier provided above.

- If the argument looks like a label (e.g. `ISS-12`, `DEC-3`, `SPEC-1`), first call `vibecheck_list` to find the matching context ID, then call `vibecheck_get` with that ID.
- If the argument looks like a UUID, call `vibecheck_get` directly.

Present the context in a readable format:

**Title** (label)
- **Type:** issue | **Status:** open | **Layer:** work
- **Tags:** severity:low, area:frontend
- **Created:** 2026-03-09

**Brief:**
> (the brief content)

**Linked sessions:** (list any linked sessions)
**Successors:** (list any successor contexts)

If the context is not found, say so and suggest using `/vibe:contexts` to browse available contexts.
