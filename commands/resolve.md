---
description: Resolve a context (issue, spec, etc.) from the VibeCheck dashboard
---

Resolve the specified context(s) in the VibeCheck dashboard.

Context IDs to resolve (space-separated): $ARGUMENTS

Accepts either the UUID returned by `/vibecheck:review` or the ISS-XX label shown on the dashboard.
Use the ID exactly as returned — do not guess.

For each ID in the arguments, call:

```
vibecheck_resolve(id="<ID>")
```

After each call, report to the user:
- Which contexts were resolved
- Which were not found
- Any errors

If no arguments are provided, explain usage:
  `/vibecheck:resolve ISS-33` — resolve by ISS-XX label
  `/vibecheck:resolve 3f8a1b2c-...` — resolve by UUID
  `/vibecheck:resolve ISS-33 ISS-34` — resolve multiple at once
