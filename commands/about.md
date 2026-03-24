---
description: Show what VibeCheck does and list all available commands
allowed-tools: Bash
---

Tell the user about VibeCheck and its available commands.

Check whether the VibeCheck dashboard is currently reachable:

```bash
_VC_CONF="$HOME/.config/vibecheck/config"; _VC_URL="${VIBECHECK_API_URL:-$(grep '^api_url=' "$_VC_CONF" 2>/dev/null | cut -d= -f2-)}"; _VC_URL="${_VC_URL%/}"; _VC_URL="${_VC_URL:-http://localhost:8420}"; curl -s --max-time 2 "$_VC_URL/api/status" 2>/dev/null && echo "REACHABLE" || echo "UNREACHABLE"
```

Then respond with the following, adjusting the status line based on the result above:

---

**VibeCheck** is a local dashboard that watches your Claude Code sessions in real time. It tracks what you're working on, flags issues before they ship, and gives you a live window into what Claude is doing across all your projects.

It connects to your configured VibeCheck server (default: `http://localhost:8420`; set `api_url=...` in `~/.config/vibecheck/config` to point to a different server). As you work, it automatically records progress — but you can also talk to it directly using the commands below.

**Dashboard status:** (reachable / not running — start it with `python -m vibecheck`)

---

**Core workflow**

| Command | What it does |
|---|---|
| `/vibecheck:review` | Review staged changes for bugs before committing |
| `/vibecheck:fix <ID>` | Investigate and fix a flagged issue |
| `/vibecheck:implement <ID>` | Begin implementing a spec — loads full context before you write a line |
| `/vibecheck:improve` | Run the improve pass manually — refines skills based on session friction |
| `/vibecheck:resolve <ID>` | Close a specific issue or spec mid-session |
---

**Context Library**

The Context Library stores specs, decisions, issues, and notes that persist across sessions.

| Command | What it does |
|---|---|
| `/vibecheck:create <title>` | Capture a new note, issue, spec, or decision |
| `/vibecheck:search <query>` | Find semantically related contexts before making a decision |
| `/vibecheck:shape <ID>` | Develop a context interactively — great for specs that aren't ready yet |
| `/vibecheck:contexts [filters]` | Browse everything in the library |
| `/vibecheck:context <ID>` | View full detail for a specific context |

> **`shape`** is where the magic is. Not sure what to build or how to frame a problem? `/vibecheck:shape` walks you through it before you write a line of code.

**Create syntax:**
- `/vibecheck:create Add rate limiting` — creates a note
- `/vibecheck:create spec: Rate limiting for summarizer | Prevent LLM cost overruns` — spec with brief
- `/vibecheck:create decision: Use PostgreSQL` — decision
- `/vibecheck:create issue: Auth tokens not invalidated on logout`

---

**Typical workflow**

1. Work normally — VibeCheck tracks progress automatically.
2. Before committing, run `/vibecheck:review` to catch issues in staged changes.
3. Fix flagged issues with `/vibecheck:fix <ID>`, then `/vibecheck:resolve <ID>` to close each one.
4. When done, commit your changes.

**Spec workflow**

1. Capture the idea: `/vibecheck:create spec: What you want to build`
2. Develop it: `/vibecheck:shape <ID>`
3. Build it: `/vibecheck:implement <ID>`
4. Close it: `/vibecheck:resolve <ID>`

---

**MCP tools** (available directly in Claude Code conversations)

| Tool | What it does |
|---|---|
| `vibecheck_update` | Post a progress checkpoint to the dashboard |
| `vibecheck_create_context` | Create a context (issue, spec, decision, note) |
| `vibecheck_update_context` | Update an existing context's brief or status |
| `vibecheck_get_context` | Load full detail for a context by ID |
| `vibecheck_list_contexts` | Browse contexts with optional filters |
| `vibecheck_discover` | Find relevant contexts by semantic query |
| `vibecheck_find_related` | Find contexts related to a given context ID |
| `vibecheck_link_context` | Link a context to the current session/objective |
| `vibecheck_get_active_context_set` | Load full active context set for a context |
| `vibecheck_resolve` | Mark a context resolved |
| `vibecheck_push_review` | Submit structured review findings (used by `/vibecheck:review`) |
| `vibecheck_begin_completion` | Start the objective completion protocol |
| `vibecheck_finalize_objective` | Finalize and close the current objective |
| `vibecheck_implement` | Begin implementing a spec from the library |

---

| `/vibecheck:about` | Show this message |
