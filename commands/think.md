---
description: Start an interactive thinking conversation to develop a context (e.g. spec, decision)
---

Shape a VibeCheck context through an interactive conversation.

**Arguments:** $ARGUMENTS

---

## Step 0 — Pre-flight (run before anything else)

### 0.1 — Specialty override
Does the input explicitly name a specialty ("design", "product", "strategy", "CEO")?
If yes, skip Steps 0.3–0.4 — route directly to that specialty in Step 3 and proceed.

### 0.2 — Reachability check
Call GET /api/status. If it fails, wait 2 seconds and retry once.
If it fails again: enter degraded mode — tell the user, shape in-memory. Do NOT abort. See "Degraded Mode" section.

### 0.3 — Workspace review
Read the workspace before asking any question:
- Read `CLAUDE.md` (project instructions, conventions, constraints)
- Run `git log --oneline -10` and `git status` (what's actively in flight)
- If the input topic clearly references a part of the codebase, read those files or run a targeted grep

### 0.4 — Context library search
- Call `vibecheck_find_related` on the input topic; read the top 1–3 results
- If the input explicitly references a known artifact (skill ID, spec label, file path), read it directly

### Surface findings
Show a one-line summary to the user before proceeding:
*"Read CLAUDE.md + git log. Found N related contexts: X, Y — using these to frame the conversation."*
This lets the user correct a bad match before the conversation begins. If nothing relevant was found, say so — that's also useful signal.

---

## Step 1 — Detect entry path

Classify `$ARGUMENTS`:

- **No argument / empty** → Path A: ask user what to shape
- **Matches `^[A-Z]+-\d+$`** (e.g. `SPEC-42`, `ISS-7`) OR resolves via API → Path C: existing context
- **Anything else** → Path B: free-text seed

---

## Path A — No argument

Ask the user one question: "What do you want to shape?" Wait for their answer, then create a spec context using the Path B `vibecheck_create_context` call (using their answer as the title seed). Extract the context ID. Then proceed to Step 3.

**The anchor must exist before the first question.**

---

## Path B — Free-text seed

Create a spec context to anchor the conversation:

```
vibecheck_create_context(
  title="Spec: <seed topic>",
  type="spec",
  context_summary="Shaping: <seed topic>"
)
```

Extract the new context `id`. Proceed to Step 2.

---

## Path C — Existing context ID

Resolve the context:

```
vibecheck_get_context(id="$ARGUMENTS")
```

Read the context type and existing brief.

**If the resolved context has `type=issue`:**
1. Tell the user: "This is an issue — shaping it will produce a new spec. The issue will be linked as a predecessor."
2. Create a new spec: `vibecheck_create_context(title="Spec: <issue title>", type="spec", predecessor_id="<issue_id>")`
3. Extract the new spec's id. Proceed shaping the spec (not the issue).
4. At the end (Step 4), update the issue: `vibecheck_update_context(id="<issue_id>", status="dispatched")`

Proceed to Step 2.

---

## Step 2 — Load specialty

Infer the right specialty from Phase 0 research signals — do not ask:
- Design / UI / visual / brand / layout → `design-consultation`
- Is-this-right / scope / strategy / should-we-build → `ceo-specialist`
- User / problem / pain / persona / who-is-this-for → `product-specialist`
- Ambiguous after Phase 0 → infer based on the strongest signal; state the inference: *"I'm treating this as a product question — correct me if wrong."*

Discover and load:

```
vibecheck_discover(query="<routing signal>", skill_type="shape", limit=4)
vibecheck_get_context(id=<matched skill id>)
```

**Load the specialty for domain expertise and final brief format.** Phase 2 below replaces the specialty's generic question flow. The specialty's domain knowledge and brief template still apply.

**After loading:** execute Phase 2 (Proposal-Reaction Loop).

---

## Phase 2 — Proposal-Reaction Loop

The specialist never opens with a question. Open with a proposal package — no preamble:

```
**[POV — primary framing]**
What this is really about: [the most interesting framing of the problem given Phase 0 findings]
Implication: [what follows from this framing — what it changes about the approach]

**[Interesting version]**
What if: [a more ambitious or unexpected take on the same problem]
Implication: [what it would unlock that the primary framing doesn't]

**[Contrarian take]**
The assumption worth questioning: [what everyone assumes but Phase 0 suggests might be wrong]
Implication: [what changes if the assumption is false]
```

End with ONE open question: *"Which of these resonates, or what did I miss?"*

**User reacts** → specialist deepens on what resonated, one exchange at a time. Ask questions only when something is genuinely unknown — not as setup.

**If the proposal misses:** ask what specifically was wrong and iterate. Do not fall back to Q1–Q4.

**If Phase 0 found nothing useful:** state it — *"I didn't find enough context to form a strong POV — here's what I have: [findings]. What's the one thing I should know?"* Then proceed once answered.

---

## Phase 3 — Premise challenge (conditional)

Trigger this only when the chosen direction has a load-bearing assumption that, if wrong, would force a mid-build pivot — e.g., *"this assumes users have X permission"* or *"this assumes the API supports Y."* Skip if no such assumption exists.

When triggered, surface 2–3 falsifiable premises:

```
PREMISES — agree or disagree:
1. [statement]
2. [statement]
3. [statement]
```

Require explicit agree/disagree per premise. If the user disagrees, revise and re-present before proceeding.

Each premise must be falsifiable — if you cannot imagine evidence that would disprove it, rewrite it.

---

## Phase A — Adversarial self-review (run before presenting the brief)

Before showing the brief, run a silent internal quality check. Do not narrate this to the user — fix issues and present the final result.

Check each dimension:
- **Completeness** — are who, pain, success, and scope all answered?
- **Consistency** — do the premises, chosen approach, and exclusions agree with each other?
- **Clarity** — would someone who wasn't in this conversation understand the spec?
- **Scope discipline** — are the exclusions real constraints or polite hedges?
- **Feasibility** — does the minimum shippable scope actually prove the core claim?

If any dimension is weak: revise the relevant section. Up to 2 revision passes. Then present.

---

## Step 4 — Apply the final brief

When the conversation is complete, apply the shaped brief to the context.

**Brief format** — the final brief must include:
- Confirmed premises (as "Foundations" section, if Phase 3 ran)
- "Why this direction" — 1-2 sentences on what in the proposal-reaction exchange confirmed the chosen framing

**Write to a file first to keep the MCP call compact:**

1. Determine the file path: `~/.vibecheck/{board_slug}/docs/{LABEL}.md` where `board_slug` is the slugified board name (e.g., "VibeCheck" → "vibecheck") and `LABEL` is the context label (e.g., `SPEC-42`).
2. Write the full shaped brief to that file using the Write tool.
3. Call:

```
vibecheck_update_context(id="<context_id>", brief_file="~/.vibecheck/{board_slug}/docs/{LABEL}.md")
```

**Fallback:** If board name is unknown, use `brief_replace` inline.

---

## Step 5 — Wrap up

1. Show the final shaped brief
2. Report the context label (e.g. SPEC-42) and status
3. Suggest next steps:
   - If spec: "Ready for `/vibe:plan` to structure your approach, or `/vibe:implement <label>` to go straight to implementation"
   - If design: "DESIGN.md written — ready for implementation"
   - If strategy: "Go/no-go decision captured — proceed to `/vibe:plan` if go"

---

## Degraded Mode (VibeCheck unreachable)

When the API is unreachable:

1. Tell the user: "VibeCheck isn't reachable — shaping in-memory. I'll offer to persist when available."
2. Skip Steps 0.3–0.4 (no context library search). Proceed with workspace review only.
3. Run the full conversation (Phases 2, 3, and A) in-memory.
4. At the end, present the shaped brief as markdown.
5. Offer: "VibeCheck is still unreachable. Here's the brief — paste it into the context manually, or retry when the server is back."

Shape always works. The server is for the brief, not the conversation.

---

## Conversation quality rules

- **Proposals over questions** — if Phase 0 gives you enough to form a POV, lead with it. Questions are for when something is genuinely unknown, not for setup.
- Research before opening — Step 0 findings are what make the proposal non-generic; never skip them
- Ask one question at a time — the most important one, not a list
- If the proposal misses, ask what was wrong — do not fall back to Q1–Q4
- State recommendations directly — no menus of equal options
- Do not recap what the user just said — move forward
- Brief depth: match complexity. MCP has no meaningful size limit. Write complete methodology.
