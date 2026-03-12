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
| `/vibecheck:resolve <ID>` | Close a specific issue or spec mid-session |
| `/vibecheck:complete` | Wrap up the current session objective and mark it done |

> **`resolve` vs `complete`:** Use `resolve <ID>` when you've fixed one specific issue and want to close it while the session continues. Use `complete` when you're done with the whole task — it closes the session objective.

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
4. When the task is done, run `/vibecheck:complete`.

**Spec workflow**

1. Capture the idea: `/vibecheck:create spec: What you want to build`
2. Develop it: `/vibecheck:shape <ID>`
3. Build it: `/vibecheck:implement <ID>`
4. Close it: `/vibecheck:resolve <ID>` (or handled automatically by `/vibecheck:complete`)

---

| `/vibecheck:about` | Show this message |
