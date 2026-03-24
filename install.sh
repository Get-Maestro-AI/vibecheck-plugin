#!/usr/bin/env bash
# VibeCheck Plugin Installer
#
# Installs the VibeCheck plugin for Claude Code:
#   - Hooks       → ~/.claude/settings.json  (safe merge, never overwrites unrelated hooks)
#   - MCP server  → claude mcp add (user scope)
#   - Commands    → ~/.claude/commands/vibecheck/*.md (symlinks)
#
# Safe to re-run (idempotent).
#
# Usage:
#   bash install.sh
#   bash install.sh --dry-run
#   VIBECHECK_API_KEY=vc_xxx VIBECHECK_API_URL=https://vibecheck.getmaestro.ai bash install.sh

set -euo pipefail

# ── curl | sh bootstrap ───────────────────────────────────────────────────────
# When piped from curl, BASH_SOURCE[0] is empty and local files don't exist.
# Download the plugin to a permanent location and re-exec from there.

PLUGIN_INSTALL_DIR="$HOME/.claude/plugins/vibecheck"
PLUGIN_REPO="https://github.com/Get-Maestro-AI/vibecheck-plugin"

_is_piped() {
  # Running piped if BASH_SOURCE[0] is unset/empty OR scripts/ dir is missing
  [[ -z "${BASH_SOURCE[0]:-}" ]] || [[ ! -d "$(dirname "${BASH_SOURCE[0]:-/dev/null}")/scripts" ]]
}

if _is_piped; then
  echo "Downloading VibeCheck plugin to $PLUGIN_INSTALL_DIR ..."
  if [[ -d "$PLUGIN_INSTALL_DIR/.git" ]]; then
    echo "Existing install found — pulling latest ..."
    git -C "$PLUGIN_INSTALL_DIR" pull --ff-only --quiet
  elif command -v git &>/dev/null; then
    git clone --depth 1 "$PLUGIN_REPO" "$PLUGIN_INSTALL_DIR"
  else
    # Fallback: download tarball via curl
    TMP_TAR="$(mktemp -t vibecheck-plugin.XXXXXX.tar.gz)"
    curl -sSfL "$PLUGIN_REPO/archive/refs/heads/main.tar.gz" -o "$TMP_TAR"
    mkdir -p "$PLUGIN_INSTALL_DIR"
    tar -xzf "$TMP_TAR" -C "$PLUGIN_INSTALL_DIR" --strip-components=1
    rm -f "$TMP_TAR"
  fi
  exec bash "$PLUGIN_INSTALL_DIR/install.sh" "$@"
fi

# ── Colors ────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $*"; }
warn() { echo -e "${YELLOW}!${RESET} $*"; }
err()  { echo -e "${RED}✗${RESET} $*" >&2; }
step() { echo -e "\n${BOLD}${BLUE}▶ $*${RESET}"; }

DRY_RUN=false
for arg in "$@"; do
  [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
done

# ── Resolve paths ─────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
COMMANDS_SRC="$SCRIPT_DIR/commands"
MCP_SERVER="$SCRIPT_DIR/servers/vibecheck-mcp/server.py"
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

# Prefer repo venv (developer install: plugin lives at repo/vibecheck-plugin/).
# Fall back to system python3 for standalone plugin distribution.
VENV_PYTHON="$(dirname "$SCRIPT_DIR")/.venv/bin/python3"
if [[ -f "$VENV_PYTHON" ]]; then
  PYTHON="$VENV_PYTHON"
else
  PYTHON="python3"
fi

echo ""
echo -e "${BOLD}VibeCheck Plugin Installer${RESET}"
echo "────────────────────────────────────────"

# ── Prerequisites ─────────────────────────────────────────────────────────────

step "Checking prerequisites"

# Python 3.9+
if ! "$PYTHON" --version &>/dev/null; then
  err "Python not found at $PYTHON"
  exit 1
fi
PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  err "Python 3.9+ required (found $PY_VERSION). Please upgrade."
  exit 1
fi
ok "Python $PY_VERSION ($PYTHON)"

# Claude Code config dir
if [[ ! -d "$CLAUDE_DIR" ]]; then
  err "Claude Code config directory not found at $CLAUDE_DIR."
  err "Install Claude Code first: https://claude.ai/download"
  exit 1
fi
ok "Claude Code config found at $CLAUDE_DIR"

# Claude CLI (for mcp add)
if ! command -v claude &>/dev/null; then
  err "'claude' CLI not found in PATH. Install Claude Code and ensure it's in your PATH."
  exit 1
fi
ok "Claude CLI found"

# MCP server script
if [[ ! -f "$MCP_SERVER" ]]; then
  err "MCP server not found at $MCP_SERVER"
  exit 1
fi
ok "MCP server found"

# ── Configuration ─────────────────────────────────────────────────────────────

step "Configuration"

if [[ -z "${VIBECHECK_API_URL:-}" ]]; then
  read -r -p "  VibeCheck server URL [https://vibecheck.getmaestro.ai]: " API_URL
  VIBECHECK_API_URL="${API_URL:-https://vibecheck.getmaestro.ai}"
fi
ok "API URL: $VIBECHECK_API_URL"

if [[ -z "${VIBECHECK_API_KEY:-}" ]]; then
  read -r -s -p "  VibeCheck API key: " API_KEY
  echo ""
  VIBECHECK_API_KEY="${API_KEY:-}"
fi
if [[ -z "$VIBECHECK_API_KEY" ]]; then
  err "An API key is required. Get yours at https://vibecheck.getmaestro.ai"
  exit 1
fi
ok "API key: set"

# ── Dry run ───────────────────────────────────────────────────────────────────

if $DRY_RUN; then
  step "Dry run — nothing written"
  echo "  Hooks    → $SETTINGS_FILE"
  echo "  MCP      → claude mcp add vibecheck (user scope)"
  echo "  Commands → $HOME/.claude/commands/vibecheck/"
  exit 0
fi

# ── Write ~/.config/vibecheck/config ─────────────────────────────────────────

step "Writing config"

mkdir -p "$HOME/.config/vibecheck"
cat > "$HOME/.config/vibecheck/config" <<EOF
api_url=$VIBECHECK_API_URL
api_key=$VIBECHECK_API_KEY
EOF
ok "Config written to ~/.config/vibecheck/config"

# ── Plugin venv (standalone installs) ────────────────────────────────────────
# Create a local venv with mcp + certifi before hooks are registered so that
# all hook scripts run under the venv python (certifi fixes SSL cert errors on
# macOS with python.org Python installs that haven't run Install Certificates).

if [[ "$PYTHON" == "python3" ]]; then
  VENV_DIR="$SCRIPT_DIR/.venv"
  if [[ ! -d "$VENV_DIR" ]]; then
    step "Setting up plugin dependencies"
    if command -v uv &>/dev/null; then
      uv venv "$VENV_DIR" --python python3 --quiet
      uv pip install --python "$VENV_DIR/bin/python3" mcp certifi --quiet
    else
      python3 -m venv "$VENV_DIR"
      "$VENV_DIR/bin/pip" install mcp certifi --quiet
    fi
  fi
  PYTHON="$VENV_DIR/bin/python3"
  ok "Plugin venv: $VENV_DIR"
fi

# ── Hooks → ~/.claude/settings.json ──────────────────────────────────────────

step "Configuring Claude Code hooks"

# Back up settings before modifying.
if [[ -f "$SETTINGS_FILE" ]]; then
  cp "$SETTINGS_FILE" "${SETTINGS_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
fi

"$PYTHON" - <<PYEOF
import json, sys, os

settings_file = "$SETTINGS_FILE"
scripts_dir   = "$SCRIPTS_DIR"
python_exe    = "$PYTHON"

# All hooks owned by VibeCheck.
# identity: substring of the command used to find/replace the hook on re-runs.
# options:  extra JSON fields (async, timeout). Empty dict = no extra fields.
OUR_HOOKS = {
    "SessionStart": [
        {
            "identity": "[VibeCheck] Session started",
            "command": "echo '[VibeCheck] Session started. Use vibecheck_update for progress checkpoints. After substantial work, run /vibecheck:review.'",
            "options": {},
        },
        {
            "identity": "health_check.py",
            "command": f"{python_exe} {scripts_dir}/health_check.py",
            "options": {"async": True, "timeout": 5},
        },
        {
            "identity": "session_baseline.py",
            "command": f"{python_exe} {scripts_dir}/session_baseline.py",
            "options": {"async": True, "timeout": 15},
        },
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {"async": True},
        },
        {
            "identity": "scan_artifacts.py",
            "command": f"{python_exe} {scripts_dir}/scan_artifacts.py",
            "options": {"async": True, "timeout": 15},
        },
    ],
    "UserPromptSubmit": [
        {
            "identity": "context_inject.py",
            "command": f"{python_exe} {scripts_dir}/context_inject.py",
            "options": {"timeout": 5},
        },
        {
            "identity": "[VibeCheck] Call vibecheck_update",
            "command": "echo '[VibeCheck] Call vibecheck_update at phase transitions. After substantial work, run /vibecheck:review.'",
            "options": {},
        },
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {"async": True},
        },
    ],
    "PreToolUse": [
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {"async": True},
        },
    ],
    "PostToolUse": [
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {"async": True},
        },
        {
            "identity": "[VibeCheck] Plan mode exited",
            "command": "echo '[VibeCheck] Plan mode exited. If the plan was not saved to VibeCheck, save it now using vibecheck_create_context(type=plan) and POST to /api/push/vc-plan before proceeding.'",
            "options": {},
            "matcher": "ExitPlanMode",
        },
        {
            "identity": "capture_artifact.py",
            "command": f"{python_exe} {scripts_dir}/capture_artifact.py",
            "options": {"timeout": 5},
            "matcher": "Write|Edit",
        },
    ],
    "PostToolUseFailure": [
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {"async": True},
        },
    ],
    "SubagentStart": [
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {"async": True},
        },
    ],
    "SubagentStop": [
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {"async": True},
        },
    ],
    "Stop": [
        {
            "identity": "push_turn.py",
            "command": f"{python_exe} {scripts_dir}/push_turn.py",
            "options": {"async": True, "timeout": 10},
        },
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {"async": True},
        },
    ],
    "SessionEnd": [
        {
            "identity": "session_summary.py",
            "command": f"{python_exe} {scripts_dir}/session_summary.py",
            "options": {"timeout": 15},
        },
        {
            "identity": "post_session_inspect.py",
            "command": f"{python_exe} {scripts_dir}/post_session_inspect.py",
            "options": {"async": True, "timeout": 25},
        },
        # Intentionally synchronous (no async) — ensures the event is flushed
        # before the process exits.
        {
            "identity": "push_event.py",
            "command": f"{python_exe} {scripts_dir}/push_event.py",
            "options": {},
        },
    ],
}

try:
    with open(settings_file) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

settings.setdefault("hooks", {})

def upsert_hook(event_name, identity, command, options, matcher=None):
    """Add or update a single hook for an event.

    Matches by identity substring — replaces the entire hook entry in place
    if found (handles message/option changes cleanly), appends a new group
    if not. Never duplicates. Never touches unrelated hooks.

    If matcher is provided, the hook group will include a "matcher" key so
    the hook only fires when the tool name matches (e.g. "ExitPlanMode").
    """
    existing = settings["hooks"].get(event_name, [])
    entry = {"type": "command", "command": command, **options}

    for group in existing:
        for i, h in enumerate(group.get("hooks", [])):
            if identity in h.get("command", ""):
                # Replace in place so option changes (async, timeout) take effect.
                group["hooks"][i] = entry
                if matcher:
                    group["matcher"] = matcher
                else:
                    group.pop("matcher", None)
                settings["hooks"][event_name] = existing
                return

    # Not found — append a new group.
    new_group = {"hooks": [entry]}
    if matcher:
        new_group["matcher"] = matcher
    existing.append(new_group)
    settings["hooks"][event_name] = existing

for event_name, hooks in OUR_HOOKS.items():
    for hook in hooks:
        upsert_hook(event_name, hook["identity"], hook["command"], hook["options"], hook.get("matcher"))

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print("ok")
PYEOF

ok "Hooks registered in $SETTINGS_FILE"
ok "  SessionStart      → health_check, session_baseline, push_event, artifact scan"
ok "  UserPromptSubmit  → context_inject, push_event"
ok "  PreToolUse        → push_event"
ok "  PostToolUse       → push_event, ExitPlanMode save-reminder, artifact capture (Write|Edit)"
ok "  PostToolUseFailure→ push_event"
ok "  SubagentStart/Stop→ push_event"
ok "  Stop              → push_turn, push_event"
ok "  SessionEnd        → session_summary, post_session_inspect, push_event"

# ── MCP server → claude mcp add ──────────────────────────────────────────────

step "Registering MCP server"

MCP_ENV_ARGS=(
  --env "VIBECHECK_API_URL=$VIBECHECK_API_URL"
  --env "VIBECHECK_API_KEY=$VIBECHECK_API_KEY"
)

# Remove any existing registration before re-adding (idempotent).
claude mcp remove vibecheck --scope user >/dev/null 2>&1 || true

claude mcp add vibecheck \
  --scope user \
  --transport stdio \
  "${MCP_ENV_ARGS[@]}" \
  -- "$PYTHON" "$MCP_SERVER"

ok "MCP server registered (user scope)"

# ── Slash commands → ~/.claude/commands/vibecheck/ ────────────────────────────

step "Installing slash commands"

COMMANDS_DEST="$HOME/.claude/commands/vibecheck"
mkdir -p "$COMMANDS_DEST"

# Remove legacy symlinks from old command names.
for legacy in checkpoint dismiss-issue find-related create-context create-issue complete; do
  if [[ -L "$COMMANDS_DEST/$legacy.md" ]]; then
    rm -f "$COMMANDS_DEST/$legacy.md"
    warn "Removed legacy command: $legacy"
  fi
done

for cmd_file in "$COMMANDS_SRC"/*.md; do
  cmd_name="$(basename "$cmd_file")"
  ln -sf "$cmd_file" "$COMMANDS_DEST/$cmd_name"
  ok "  /vibecheck:${cmd_name%.md}"
done

# ── Verify server connection ──────────────────────────────────────────────────

step "Verifying server connection"

if VIBECHECK_API_URL="$VIBECHECK_API_URL" VIBECHECK_API_KEY="$VIBECHECK_API_KEY" \
   "$PYTHON" "$SCRIPTS_DIR/health_check.py" 2>/dev/null; then
  ok "Server reachable at $VIBECHECK_API_URL"
else
  warn "Could not reach server at $VIBECHECK_API_URL"
  warn "Check your API key or visit https://vibecheck.getmaestro.ai"
  warn "Open a new Claude Code session once the server is reachable — hooks take effect immediately."
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${GREEN}Installation complete!${RESET}"
echo "────────────────────────────────────────"
echo ""
echo "  Restart Claude Code (or open a new session) for hooks to take effect."
echo ""
echo "  Core workflow:"
echo "    /vibecheck:review      — review changes for bugs before committing"
echo "    /vibecheck:fix <ID>    — investigate and fix a flagged issue"
echo "    /vibecheck:implement   — begin a spec with full context loaded"
echo "    /vibecheck:improve     — refine skills based on session friction"
echo "    /vibecheck:shape       — develop a context interactively"
echo ""
echo "  Context Library:"
echo "    /vibecheck:create      — capture a note, issue, spec, or decision"
echo "    /vibecheck:search      — find semantically related contexts"
echo "    /vibecheck:contexts    — browse all contexts"
echo ""
echo "  To uninstall: claude mcp remove vibecheck --scope user"
echo ""
