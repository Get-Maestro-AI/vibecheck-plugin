# Reviewing Procedure

## Contents
- Step 1: Fetch scoped file list from VibeCheck
- Step 2: Union with recent report context
- Step 3: Get targeted diff
- Step 4: Launch background review subagent
- Validation checklist

---

## Step 1 — Fetch the scoped file list from VibeCheck

Run `scripts/get-objective-files.sh` (in your current context, not the subagent):

```bash
bash scripts/get-objective-files.sh
```

The script returns one file path per line. If VibeCheck is unreachable, it prints nothing and exits 0.

## Step 2 — Union with recent report context

Union the output from Step 1 with any `files_modified` from `vibecheck_update` progress calls still in your context. If both sources are empty, derive the file list from your Edit/Write tool calls since the last `"implementing"` checkpoint update.

**Do not proceed with an empty file list** — an empty list means the review covers nothing. Derive the list from your own tool history if needed.

## Step 3 — Get a targeted diff of only those files

```bash
git diff HEAD -- <file1> <file2> ...
```

Use `HEAD`, NOT `--cached` — this catches all uncommitted changes to those files, not just staged ones.

## Step 4 — Launch a background review subagent

Use the Task tool with `run_in_background: true` and `subagent_type: "general-purpose"`.

Pass the subagent:
- **Task goal**: your checkpoint summary (what you just built and why)
- **Files to review**: the scoped list from Steps 1–2
- **Diff**: the full output of the `git diff HEAD` from Step 3, embedded inline in the prompt
- **Instructions**: Review only the provided diff for correctness bugs, fragile assumptions, unhandled edge cases, error handling gaps, security risks, concurrency issues, performance risks, breaking API changes, and missing validation. POST findings to `http://localhost:8420/api/push/vc-review` with `staged_files` set to the scoped file list. Do NOT make code changes or dismiss issues — your only job is to analyze and report. Use the payload schema in `references/vc-review-schema.md`.

**The subagent reviews only the diff you provide — it does NOT run git commands itself.**

Do not wait for the subagent to complete. Continue your own work in parallel. The review runs independently and surfaces results to the VibeCheck dashboard.

---

## Validation checklist

Before continuing after launching the subagent, confirm:

- [ ] Subagent launched with `run_in_background: true`
- [ ] `files` list passed to the subagent is non-empty (not reviewing nothing)
- [ ] Diff was embedded inline in the subagent prompt (not passed as a command to run)
