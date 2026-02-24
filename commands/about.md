---
description: Show what VibeCheck does and list all available commands
allowed-tools: Bash
---

Tell the user about VibeCheck and its available commands.

Check whether the VibeCheck dashboard is currently reachable:

```bash
curl -s --max-time 2 http://localhost:8420/api/status 2>/dev/null && echo "REACHABLE" || echo "UNREACHABLE"
```

Then respond with the following, adjusting the status line based on the result above:

---

**VibeCheck** is a local dashboard that watches your Claude Code sessions in real time. It tracks what you're working on, flags issues before they ship, and gives you (and anyone else watching) a live window into what Claude is doing across all your projects.

It runs in the background at `http://localhost:8420`. As you work, it automatically records progress — but you can also talk to it directly using the commands below.

**Dashboard status:** (reachable / not running — start it with `python -m vibecheck`)

---

**Commands**

| Command | What it does |
|---|---|
| `/vibecheck:review` | Review staged changes for bugs before committing |
| `/vibecheck:fix <ID>` | Walk through and fix a flagged issue (e.g. `/vibecheck:fix VC-401`) |
| `/vibecheck:complete` | Wrap up the current task: review code and mark the objective done |
| `/vibecheck:create-issue <description>` | Flag a problem so it appears in the dashboard |
| `/vibecheck:dismiss-issue <ID>` | Clear a resolved issue from the dashboard |
| `/vibecheck:update <JSON>` | Post a progress checkpoint to the dashboard |
| `/vibecheck:about` | Show this message |

---

**Typical workflow**

1. Work normally — VibeCheck tracks progress automatically in the background.
2. Before committing, run `/vibecheck:review` to catch issues in staged changes.
3. If issues are found, use `/vibecheck:fix <ID>` to investigate and resolve them.
4. Once everything looks good, run `/vibecheck:complete` to close out the task.
