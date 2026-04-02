# VibeCheck Plugin — Public Distribution

## Install

```bash
curl -sSf https://raw.githubusercontent.com/Stratulus/vibecheck-plugin/main/install.sh | sh
```

Or with your API key pre-set (e.g. for invite links):

```bash
VIBECHECK_API_KEY=vc_xxx curl -sSf https://raw.githubusercontent.com/Stratulus/vibecheck-plugin/main/install.sh | sh
```

You will be prompted for:
- **Server URL** — defaults to `https://vibecheck.getmaestro.ai`
- **API key** — required; get yours at https://vibecheck.getmaestro.ai

## What the installer does

1. Downloads the plugin to `~/.claude/plugins/vibecheck/` (via `git clone`)
2. Writes `~/.config/vibecheck/config` with your `api_url` and `api_key`
3. Registers Claude Code lifecycle hooks in `~/.claude/settings.json`
4. Creates a local `.venv` with the `mcp` library for the MCP server
5. Registers the MCP server via `claude mcp add` (user scope)
6. Symlinks slash commands into `~/.claude/commands/vibe/`

Safe to re-run — idempotent. Re-running pulls the latest plugin via `git pull`.

## Uninstall

```bash
claude mcp remove vibecheck --scope user
```

Then remove hooks from `~/.claude/settings.json` and delete `~/.claude/plugins/vibecheck/`.

## Slash commands

| Command | Description |
|---|---|
| `/vibe:review` | Check your work at any phase before committing |
| `/vibe:fix <ID>` | Investigate and fix a flagged issue |
| `/vibe:build <ID>` | Begin implementing a spec with full context |
| `/vibe:think <ID>` | Develop a context interactively |
| `/vibe:create` | Capture a note, issue, spec, or decision |
| `/vibe:search` | Find semantically related contexts |
| `/vibe:contexts` | Browse all contexts |
| `/vibe:context <ID>` | View a specific context |
| `/vibe:resolve <ID>` | Resolve an issue or spec |
| `/vibe:about` | Show VibeCheck info and all commands |

## Publishing the public repo

The `vibecheck-plugin/` directory is the root of the public repo. To publish:

```bash
# From the vibecheck2 monorepo root:
git subtree split --prefix vibecheck-plugin -b vibecheck-plugin-standalone
git push git@github.com:Get-Maestro-AI/vibecheck-plugin.git vibecheck-plugin-standalone:main
```

To update after changes to `vibecheck-plugin/`:

```bash
git subtree split --prefix vibecheck-plugin -b vibecheck-plugin-standalone --rejoin
git push git@github.com:Get-Maestro-AI/vibecheck-plugin.git vibecheck-plugin-standalone:main
```
