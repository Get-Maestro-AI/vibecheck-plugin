---
description: Start an interactive shaping conversation to develop a context (e.g. spec, decision)
---

Shape a VibeCheck context through an interactive conversation.

**Arguments:** $ARGUMENTS

---

## Step 0 — Pre-flight checks (run before anything else)

1. **Explicit specialist override:** Does the input contain a specialist name
   ("Mara", "design specialist", "Marcus", "product specialist", "CEO specialist")?
   If yes, skip all routing logic — load that specialist directly (Step 2) and proceed.

2. **Reachability check:** Call GET /api/status. If it fails, wait 2 seconds and retry once.
   If it fails again (connection refused, timeout, or error response):
   enter degraded mode — tell the user, shape in-memory.
   Do NOT abort. See "Degraded Mode" section.

---

## Step 1 — Detect entry path

Classify `$ARGUMENTS`:

- **No argument / empty** → no-ID path: ask user what to shape, then route to sub-specialist
- **Matches `^[A-Z]+-\d+$`** (e.g. `SPEC-42`, `ISS-7`) OR resolves via API → existing context path
- **Anything else** → free-text seed path: use as topic, route to sub-specialist, create spec

---

## Path A — No argument

Ask the user one question: "What do you want to shape?" Wait for their answer, then route to the appropriate sub-specialist based on their response:

- Design / UI / visual / brand / color / font / layout → `design-consultation`
- Is-this-right / scope / CEO / opportunity / strategy / should-we-build → `ceo-specialist`
- User / problem / pain / persona / who-is-this-for → `product-specialist`
- Ambiguous → ask ONE clarifying question: "Is this mainly about the design direction, the strategy/scope, or the user problem?"

Once you know what the user wants to shape, create a spec context using the Path B `vibecheck_create_context` call (using their answer as the title seed). Extract the context ID. Then load the sub-specialist and conduct the shaping conversation, logging all turns with the context ID.

**The anchor must exist before the first specialist question.**

---

## Path B — Free-text seed

Use the free-text as the seed topic. Route to sub-specialist using the same signals as Path A.

Then create a spec context to anchor the conversation:

```
vibecheck_create_context(
  title="Spec: <seed topic>",
  type="spec",
  context_summary="Shaping: <seed topic>"
)
```

Extract the new context `id` from the response. Proceed with this context ID as the anchor. Conduct the shaping conversation using the loaded sub-specialist's methodology (see Step 3).

---

## Path C — Existing context ID

Resolve the context:

```
vibecheck_get_context(id="$ARGUMENTS")
```

Read the context type and existing brief/conversation. Route to sub-specialist based on context type:
- `type=spec` with design signals → `design-consultation`
- `type=spec` with strategy signals → `ceo-specialist`
- `type=spec` or `type=issue` with user/problem signals → `product-specialist`
- No clear signal → ask: "Is this mainly design direction, strategy/scope, or user problem?"

**If the resolved context has `type=issue`:**
1. Tell the user: "This is an issue — shaping it will produce a new spec. The issue will be linked as a predecessor."
2. Create a new spec: `vibecheck_create_context(title="Spec: <issue title>", type="spec", predecessor_id="<issue_id>")`
3. Extract the new spec's id. Proceed shaping the spec (not the issue).
4. At the end of the conversation (Step 4), update the issue status to dispatched:
   `vibecheck_update_context(id="<issue_id>", status="dispatched")`

---

## Step 2 — Load the sub-specialist

Discover the sub-specialist skill:

```
vibecheck_discover(query="<routing signal>", skill_type="shape", limit=4)
```

Load the full brief of the matched skill:
```
vibecheck_get_context(id=<matched skill id>)
```

**The sub-specialist brief is the methodology. Follow it exactly — do not improvise.**

Available sub-specialists:
- `design-consultation` — Mara Chen, design system + DESIGN.md
- `product-specialist` — Marcus Webb, user/problem/scope clarity
- `ceo-specialist` — Marcus Webb in strategic mode, go/no-go + operating mode

---

## Step 1a — Brief assessment (run before asking anything)

After loading the sub-specialist, before asking any question:

Check which of the four product dimensions are already answered in the user's
input and/or the context brief:
- Q1 (Who is this for?) — Is a specific human or the user themselves described?
- Q2 (What pain?) — Is a concrete friction or failure mode described?
- Q3 (What does success look like?) — Is an outcome or before/after described?
- Q4 (Minimum scope?) — Are there explicit changes, inclusions, or exclusions?

Determine dialog mode:

**REFINEMENT MODE (>=2 dimensions answered):**
Open with a synthesis paragraph — "Here's what I'm taking from what you
said: [1-paragraph summary of the job to be done]."
Then ask at most ONE question about the single most critical unanswered dimension.
Turn budget: 0–1 questions. If all four dimensions are answerable, produce
the brief directly — no questions.

**DISCOVERY MODE (0–1 dimensions answered):**
Run Q1 → Q2 → Q3 → Q4 in order, one question at a time.
Turn budget: maximum 4 questions.
If you are about to ask a fifth question, produce the brief instead and mark
the unanswered dimension as an open question in the brief.

The synthesis opening in refinement mode proves you read the input. If the
synthesis is wrong, the user will correct it — faster than answering Q1 cold.

---

## Step 3 — Conduct the shaping conversation

Run the shaping conversation in-skill using the loaded sub-specialist's methodology:

- **Read before asking** — perform Step 1a before every first question. Do not open with Q1 if the user self-identified as the target user.
- **Refinement mode:** open with synthesis, ask at most 1 question.
- **Discovery mode:** Q1→Q4 in order, stop at 4. Fifth question = produce brief.
- The turn limit is a judgment call, not mechanical — but the DEFAULT is to produce the brief rather than ask another question when in doubt.
- Ask one question at a time — the most important one, not a list
- State recommendations directly — no menus of equal options
- Challenge vague language — "improve" and "uplift" are not specs
- Do not recap what the user just said — move forward

Continue until:
- The user says they're done ("that's enough", "done", "finish", "ship it")
- The sub-specialist's output is complete (e.g. product brief, strategic brief, or DESIGN.md drafted)

---

## Step 4 — Apply the final brief

When the conversation is complete, apply the shaped brief to the context:

```
vibecheck_update_context(id="<context_id>", brief_replace="<full shaped brief markdown>")
```

The applied brief must match the output of the sub-specialist's methodology exactly — do not summarize.

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
2. Proceed with the full shaping conversation.
3. At the end, present the shaped brief as markdown.
4. Offer: "VibeCheck is still unreachable. Here's the brief — paste it into the context manually, or retry when the server is back."

Shape always works. The server is for the brief, not the conversation.

---

## Conversation quality rules

- Challenge vague language — "improve" and "uplift" are not specs; ask what specifically feels wrong
- Ask one question at a time — the most important one, not a list
- State recommendations directly — no menus
- Produce concrete rewrites, not skeletons
- Do not recap what the user just said — move forward
- Brief depth: match complexity. MCP has no meaningful size limit. Write complete methodology.
