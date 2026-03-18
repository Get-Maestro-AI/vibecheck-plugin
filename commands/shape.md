---
description: Start an interactive shaping conversation to develop a context (e.g. spec, decision)
allowed-tools: Bash
---

Start a shaping conversation for a VibeCheck context.

**Context identifier:** $ARGUMENTS

## Step 1 — Load the context

First, resolve the context:

!`_VC_CONF="$HOME/.config/vibecheck/config"; _VC_KEY="${VIBECHECK_API_KEY:-$(grep '^api_key=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"; _VC_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"; _VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"; _AUTH_ARGS=(); [ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY"); curl -s --max-time 3 "${_AUTH_ARGS[@]}" "$_VC_URL/api/contexts/$ARGUMENTS" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo '{"error":"Context not found or VibeCheck unreachable"}'`

## Step 2 — Initialize or resume shaping

Check if the context already has a `shape_conversation` with entries. If so, resume from where it left off. If not, initialize a shaping session using the `id` field from Step 1:

```bash
_VC_CONF="$HOME/.config/vibecheck/config"
_VC_KEY="${VIBECHECK_API_KEY:-$(grep '^api_key=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"
_VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"
_AUTH_ARGS=()
[ -n "$_VC_KEY" ] && _AUTH_ARGS=(-H "Authorization: Bearer $_VC_KEY")
_CTX_ID="<substitute the id value from Step 1 here>"

curl -s -X POST "$_VC_URL/api/contexts/$_CTX_ID/shape/init" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d '{}' | python3 -m json.tool
```

## Step 3 — Interactive conversation

The shaping API returns questions to develop the context. Present each question to the user and collect their answer. For each answer, reuse `_CTX_ID` from Step 2:

```bash
curl -s -X POST "$_VC_URL/api/contexts/$_CTX_ID/shape" \
  -H "Content-Type: application/json" \
  "${_AUTH_ARGS[@]}" \
  -d '{"answer": "<USER_ANSWER>"}'
```

Continue the conversation until:
- The user says they're done (e.g. "that's enough", "done", "finish")
- The shaping API indicates the context is fully shaped

## Step 4 — Wrap up

Once shaping is complete:
1. Show the updated context brief
2. Report the new status
3. Suggest next steps: `/vibecheck:context <label>` to review, or the context is ready for implementation if it's a spec
