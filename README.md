# VibeCheck Plugin for Claude Code

VibeCheck is a real-time session monitoring tool for [Claude Code](https://claude.ai/code). It connects your Claude Code sessions to the VibeCheck dashboard, giving you live visibility into what Claude is doing across all your projects.

## What it does

- Posts lifecycle events (session start/end, tool calls, turn summaries) to the VibeCheck dashboard in real time
- Injects relevant context from your project's Context Library into each Claude prompt
- Adds slash commands for structured workflows: code review, issue tracking, spec implementation
- Exposes a `vibecheck_update` MCP tool that Claude uses to report progress checkpoints

## Install

```bash
curl -sSf https://raw.githubusercontent.com/Get-Maestro-AI/vibecheck-plugin/main/install.sh | sh
```

You will be prompted for your API key. Get one at **https://vibecheck.getmaestro.ai**.

## Data & Privacy

**By installing this plugin, your Claude Code session activity is sent to the VibeCheck server at `https://vibecheck.getmaestro.ai`.**

Specifically, the plugin collects and transmits:

- Session start and end events, including the working directory and git branch
- A summary of each conversation turn (tool calls made, assistant responses)
- Lifecycle hook events (prompt submitted, tool used, subagent started/stopped)
- End-of-session summaries and post-session inspection results
- Git context: current branch, recent commits, diff stats (not file contents)

This data is used to power the VibeCheck dashboard. It is associated with your API key and is not shared with third parties.

If you prefer not to send data, do not install this plugin or remove it at any time:

```bash
claude mcp remove vibecheck --scope user
```

## Slash commands

| Command | Description |
|---|---|
| `/vibe:check` | Review changes for bugs before committing |
| `/vibe:fix <ID>` | Investigate and fix a flagged issue |
| `/vibe:implement <ID>` | Begin implementing a spec with full context |
| `/vibe:shape <ID>` | Develop a context interactively |
| `/vibe:create` | Capture a note, issue, spec, or decision |
| `/vibe:search` | Find semantically related contexts |
| `/vibe:contexts` | Browse all contexts |
| `/vibe:context <ID>` | View a specific context |
| `/vibe:resolve <ID>` | Resolve an issue or spec |
| `/vibe:about` | Show all available commands |

## Requirements

- [Claude Code](https://claude.ai/code) installed and in your PATH
- Python 3.10+
- git (recommended; installer falls back to curl/tar if unavailable)

## License

MIT
