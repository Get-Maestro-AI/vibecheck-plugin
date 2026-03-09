---
description: Walk through and fix a flagged issue by ID (e.g. ISS-42)
allowed-tools: Bash, Read, Grep, Glob
---

Investigate VibeCheck issue **$ARGUMENTS** and produce a concrete fix plan.

## Context lookup

!`_VC_CONF="$HOME/.config/vibecheck/config.json"; _VC_KEY="${VIBECHECK_API_KEY:-$(sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"; _VC_URL="${VIBECHECK_API_URL:-$(sed -n 's/.*"api_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"; _VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"; _AUTH_ARGS=(); [ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY"); curl -s --max-time 3 "${_AUTH_ARGS[@]}" "$_VC_URL/api/contexts/$ARGUMENTS" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo '{"error":"Context not found or VibeCheck unreachable"}'`

## Fallback: active alerts for this project

!`_VC_CONF="$HOME/.config/vibecheck/config.json"; _VC_KEY="${VIBECHECK_API_KEY:-$(sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"; _VC_URL="${VIBECHECK_API_URL:-$(sed -n 's/.*"api_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$_VC_CONF" 2>/dev/null)}"; _VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"; _AUTH_ARGS=(); [ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY"); curl -s --max-time 3 "${_AUTH_ARGS[@]}" "$_VC_URL/api/projects/$(basename "$(pwd)")/alerts" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo '{"alerts":[],"error":"VibeCheck unreachable — is the server running?"}'`

---

## Instructions

You are in **investigation and planning mode**. Do not make any code changes yet.

**Step 1 — Find the issue**
First check the "Context lookup" result above. If it returned a valid context (has `id`, `title`, `brief`), use that as your issue. The `brief` field contains the problem description, evidence, and suggested fix.

If the context lookup failed, fall back to the "active alerts" JSON. Locate the alert where `label == "$ARGUMENTS"`. Alert labels use the format `PREFIX-N` (e.g. `VC-405`).

If both are empty or VibeCheck is unreachable, ask the user to paste the issue description before continuing.

**Step 2 — Understand the issue**
Read all available fields carefully:
- For contexts: `brief` contains the full description including problem, evidence, and suggested fix
- For alerts: `description`, `evidence`, `suggested_action`, `title`

**Step 3 — Locate the code**
Use Grep, Glob, and Read to find the specific file(s) and line(s) from the evidence. Read enough surrounding context to understand the full picture — callers, consumers, related logic.

**Step 4 — Investigate root cause**
Understand *why* the problem exists, not just where. Check whether fixing it at the identified location is sufficient or whether related call sites also need updating.

**Step 5 — Design the fix**
Determine the minimal, safe change that resolves the root cause. If there are multiple approaches with meaningfully different trade-offs, lay them out.

**Step 6 — Present the plan**
Write a numbered, step-by-step plan. For each step:
- Exact file path and location (function name or line range)
- The specific change to make
- Why this change resolves the issue

---

Once the fix is implemented, call `/vibecheck:dismiss-issue $ARGUMENTS` to clear it from the dashboard.
