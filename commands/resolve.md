---
description: Resolve an issue or context (issue, spec, etc.) from the VibeCheck dashboard
---

Resolve the specified issue(s) or context(s) in the VibeCheck dashboard.

IDs to resolve (space-separated): $ARGUMENTS

Accepts a UUID or label — works for both Issue Items (VC-ISS-XX labels) and Contexts (SPEC-XX, PLN-XX labels).
Use the ID exactly as returned — do not guess.

For each ID in the arguments, call:

```
vibecheck_resolve(id="<ID>")
```

After each call, report to the user:
- Which items/contexts were resolved
- Which were not found
- Any errors

If no arguments are provided, explain usage:
  `/vibe:resolve VC-ISS-33` — resolve a review issue by label
  `/vibe:resolve SPEC-12` — resolve a spec by label
  `/vibe:resolve 3f8a1b2c-...` — resolve by UUID
  `/vibe:resolve VC-ISS-33 VC-ISS-34` — resolve multiple at once
