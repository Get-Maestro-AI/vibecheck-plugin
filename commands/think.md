---
description: Start an interactive thinking conversation to develop a context (e.g. spec, decision)
---

Shape a VibeCheck context through an interactive conversation.

**Arguments:** $ARGUMENTS

---

## Step 0 — Pre-flight (run before anything else)

### 0.1 — Specialty override
Does the input explicitly name a specialty ("design", "product", "strategy", "CEO")?
If yes, skip Steps 0.3–0.4 and mode routing — route directly to that specialty in Step 3 and proceed.

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

Ask the user one question: "What do you want to shape?" Wait for their answer, then create a spec context using the Path B `vibecheck_create_context` call (using their answer as the title seed). Extract the context ID. Then proceed to Step 2 (mode routing).

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

## Step 2 — Mode routing (run after context is anchored)

Ask ONE mode routing question before loading any specialty:

> "Are you exploring an early idea, refining something existing, or scoping an issue into a spec?"

Route:
- **Exploring** → Phase 2B (Builder Mode) — generative, not adversarial
- **New concept with some definition** → Phase 2A (Forcing questions)
- **Refining existing** → skip to Phase 3 (Premise challenge first), then gap questions
- **Scoping an issue** → constraint mode: ask minimum shippable + explicit exclusions first, then Phase 3

**Escape hatch:** If the user says "just do it" or equivalent at any point, ask the 2 most critical unanswered questions, then proceed to Phase 4. On second pushback, proceed to Phase 4 immediately.

---

## Step 3 — Load specialty

Route to the right specialty based on the topic:
- Design / UI / visual / brand / layout → `design-consultation`
- Is-this-right / scope / strategy / should-we-build → `ceo-specialist`
- User / problem / pain / persona / who-is-this-for → `product-specialist`
- Ambiguous → ask ONE clarifying question: "Is this mainly design direction, strategy/scope, or the user problem?"

Discover and load:

```
vibecheck_discover(query="<routing signal>", skill_type="shape", limit=4)
vibecheck_get_context(id=<matched skill id>)
```

**Load the specialty for domain expertise and final brief format.** The conversation phases below (2A/2B/3/4/5) replace the specialty's generic question flow. The specialty's domain knowledge and brief template still apply.

**After loading:** execute the phase selected in Step 2 — Phase 2A, 2B, or 3 depending on the routing answer.

---

## Phase 2A — Forcing questions (New concept mode)

Adversarial questions, one at a time. Do not move on until the answer is specific. Name bad answers explicitly — do not politely accept vague responses.

**Ask only the relevant subset based on stage:**

| Stage | Ask |
|---|---|
| Pre-idea / early concept | Q1, Q2, Q3 |
| Has a defined problem | Q2, Q3, Q4 |
| Has prior attempts or existing work | Q3, Q4 |

**Q1 — Evidence of demand**
*"What's the strongest evidence someone would be upset if this didn't exist? Not 'interested' — actually upset."*
Red flag: "people say it's cool," waitlists, general enthusiasm, "developers want this."

**Q2 — Specific human**
*"Name the actual human most affected. Job title, what did they just try to do, what went wrong?"*
Red flag: categories ("developers," "users," "teams"). Push until a specific person in a specific situation is named.

**Q3 — Status quo**
*"What are they doing today instead, and what's broken about it?"*
Red flag: "nothing — there's no solution." There is always a status quo.

**Q4 — Minimum pull**
*"What's the smallest thing you could ship that would make the person from Q2 say 'I need this'?"*
Push back on over-scoped answers: "That's a full product. What's the one thing?"

---

## Phase 2B — Builder Mode (Early exploration)

Generative questions, not interrogative. For ideas that are genuinely early — forcing questions would kill momentum before the idea is worth killing.

Ask one at a time:
1. "What's the most interesting version of this — not the safest, the most interesting?"
2. "Who would you show this to first? What would make them say 'whoa'?"
3. "What's the fastest path to something you could actually use or share?"
4. "What existing thing is closest to this, and how is yours different?"

After 2–3 exchanges, offer the transition:
*"You've got enough shape here to pressure-test it. Want to?"*
- If yes → switch to Phase 2A forcing questions.
- If no answer after the next exchange → offer once more, then proceed to Phase 3 regardless.

---

## Phase 3 — Premise challenge

Before producing alternatives, surface 2–3 falsifiable premises derived from the conversation:

```
PREMISES — agree or disagree:
1. [statement]
2. [statement]
3. [statement]
```

Require explicit agree/disagree per premise. If the user disagrees with a premise, revise and re-present. Do not proceed to Phase 4 until all premises are confirmed.

Each premise must be falsifiable — if you cannot imagine evidence that would disprove it, rewrite it.

---

## Phase 4 — Mandatory alternatives

Always produce 2–3 scoped approaches. Never present a single direction.

```
APPROACH A: [Name] — Minimal Viable
  What it is: [1-2 sentences]
  Effort: [S / M / L]
  Completeness: X/10
  Included: [list]
  Excluded: [list — mandatory]

APPROACH B: [Name] — Ideal Architecture
  What it is: ...
  Effort: ...
  Completeness: X/10
  Included: ...
  Excluded: ...

APPROACH C: [Name] — Creative / Lateral  (optional, when genuinely useful)
  ...
```

**Completeness calibration:** 10 = all edge cases handled, 7 = happy path only, 3 = proves the concept exists.

One must be minimal viable, one must be ideal, one may be creative/lateral. User chooses an approach. The brief is written for the chosen approach only.

---

## Phase 5 — Adversarial self-review (run before presenting the brief)

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

**Enriched brief format** — the final brief must include:
- Confirmed premises (as "Foundations" section)
- Chosen approach's completeness score
- "Why not the alternatives" (1 line per rejected approach)

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
3. Run the full conversation (Phases 2–5) in-memory.
4. At the end, present the shaped brief as markdown.
5. Offer: "VibeCheck is still unreachable. Here's the brief — paste it into the context manually, or retry when the server is back."

Shape always works. The server is for the brief, not the conversation.

---

## Conversation quality rules

- Research before asking — never open cold; Step 0 findings anchor the conversation
- Ask one question at a time — the most important one, not a list
- Name bad answers — vague answers get named as vague, not accepted and moved past
- State recommendations directly — no menus of equal options
- Challenge vague language — "improve" and "better UX" are not specs; ask what specifically is broken
- Do not recap what the user just said — move forward
- The escape hatch is real — if the user pushes back twice, respect it immediately
- Brief depth: match complexity. MCP has no meaningful size limit. Write complete methodology.
