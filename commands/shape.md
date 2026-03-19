---
description: Start an interactive shaping conversation to develop a context (e.g. spec, decision)
allowed-tools: Bash
---

Shape a VibeCheck context through an interactive conversation.

**Arguments:** $ARGUMENTS

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

Once you know the direction, load the sub-specialist skill and conduct the shaping conversation using its methodology (see Step 3).

---

## Path B — Free-text seed

Use the free-text as the seed topic. Route to sub-specialist using the same signals as Path A.

Then create a spec context to anchor the conversation:

```bash
_VC_CONF="$HOME/.config/vibecheck/config"
_VC_KEY="${VIBECHECK_API_KEY:-$(grep '^api_key=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"
_AUTH_ARGS=(); [ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY")

_SHAPE_TITLE=$(python3 -c "import json,sys; print(json.dumps('Spec: ' + sys.argv[1]))" "$ARGUMENTS")
_SHAPE_SUMMARY=$(python3 -c "import json,sys; print(json.dumps('Shaping: ' + sys.argv[1]))" "$ARGUMENTS")

curl -s -X POST "$_VC_URL/api/contexts" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d "{\"title\": $_SHAPE_TITLE, \"type\": \"spec\", \"context_summary\": $_SHAPE_SUMMARY}" \
  | python3 -m json.tool 2>/dev/null
```

Extract the new context `id` from the response. Proceed with this context ID as the anchor. Conduct the shaping conversation using the loaded sub-specialist's methodology (see Step 3).

---

## Path C — Existing context ID

Resolve the context:

```bash
_VC_CONF="$HOME/.config/vibecheck/config"
_VC_KEY="${VIBECHECK_API_KEY:-$(grep '^api_key=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"
_AUTH_ARGS=(); [ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY")

curl -s "${_AUTH_ARGS[@]}" "$_VC_URL/api/contexts/$ARGUMENTS" \
  | python3 -m json.tool 2>/dev/null || echo '{"error":"Context not found or VibeCheck unreachable"}'
```

Read the context type and existing brief/conversation. Route to sub-specialist based on context type:
- `type=spec` with design signals → `design-consultation`
- `type=spec` with strategy signals → `ceo-specialist`
- `type=spec` or `type=issue` with user/problem signals → `product-specialist`
- No clear signal → ask: "Is this mainly design direction, strategy/scope, or user problem?"

If the context has an existing `shape_conversation`, resume from where it left off — do not restart.

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

## Step 3 — Conduct the shaping conversation

Run the shaping conversation in-skill using the loaded sub-specialist's methodology:

- Ask one question at a time — the most important one, not a list
- State recommendations directly — no menus of equal options
- Challenge vague language — "improve" and "uplift" are not specs
- Do not recap what the user just said — move forward

Log each turn to VibeCheck for persistence:

```bash
# Log a turn (substitute _CTX_ID with context id, role with user/assistant, content with message)
curl -s -X POST "$_VC_URL/api/contexts/$_CTX_ID/shape/message" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d "{\"role\": \"<role>\", \"content\": \"<content>\"}"
```

This is persistence-only — the server does NOT generate responses. You are the reasoning engine.

Continue until:
- The user says they're done ("that's enough", "done", "finish", "ship it")
- The sub-specialist's output is complete (e.g. product brief, strategic brief, or DESIGN.md drafted)

---

## Step 4 — Apply the final brief

When the conversation is complete, apply the shaped brief to the context:

```bash
curl -s -X PATCH "$_VC_URL/api/contexts/$_CTX_ID" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d "{\"brief_replace\": \"<full shaped brief markdown>\"}"
```

The applied brief must match the output of the sub-specialist's methodology exactly — do not summarize.

---

## Step 5 — Wrap up

1. Show the final shaped brief
2. Report the context label (e.g. SPEC-42) and status
3. Suggest next steps:
   - If spec: "Ready for `/vibecheck:implement <label>`"
   - If design: "DESIGN.md written — ready for implementation"
   - If strategy: "Go/no-go decision captured — proceed to `/vibecheck:plan` if go"

---

## Conversation quality rules

- Challenge vague language — "improve" and "uplift" are not specs; ask what specifically feels wrong
- Ask one question at a time — the most important one, not a list
- State recommendations directly — no menus
- Produce concrete rewrites, not skeletons
- Do not recap what the user just said — move forward
- Brief depth: match complexity. MCP has no meaningful size limit. Write complete methodology.
