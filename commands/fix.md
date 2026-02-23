---
description: Investigate a VibeCheck issue and produce a concrete fix plan. Fetches the issue context (title, description, evidence, suggested action) from the dashboard by ID, reads the relevant code, and presents step-by-step next steps. Use when the user provides a VibeCheck issue ID (e.g. 401, 402) to investigate and fix.
allowed-tools: Bash, Read, Grep, Glob
---

Investigate VibeCheck issue **$ARGUMENTS** and produce a concrete fix plan.

## Active alerts for this project

!`curl -s --max-time 3 "http://localhost:8420/api/projects/$(basename "$(pwd)")/alerts" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo '{"alerts":[],"error":"VibeCheck unreachable — is the server running?"}'`

---

## Instructions

You are in **investigation and planning mode**. Do not make any code changes yet.

**Step 1 — Find the issue**
In the JSON above, locate the alert where `label == "$ARGUMENTS"`, or whose `title` begins with `[$ARGUMENTS]`, or whose `id` equals `$ARGUMENTS` (stripped of any leading `#`). If alerts are empty or VibeCheck is unreachable, ask the user to paste the issue description before continuing.

**Step 2 — Understand the issue**
Read all four fields carefully:
- `description` — what is wrong and why it's risky
- `evidence` — the exact location (file and line/function) and which staged files are involved
- `suggested_action` — the direction of the fix
- `title` — the short label

**Step 3 — Locate the code**
Use Grep, Glob, and Read to find the specific file(s) and line(s) from the `evidence` field. Read enough surrounding context to understand the full picture — callers, consumers, related logic.

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
