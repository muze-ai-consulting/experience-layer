#!/usr/bin/env bash
# experience-layer installer — idempotent, safe to re-run
set -e

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run|-n)
      DRY_RUN=1
      ;;
    --help|-h)
      cat <<USAGE
Usage: $(basename "$0") [--dry-run|-n] [--help|-h]

Installs experience-layer for Claude Code:
  - Creates ~/.claude/experience/ corpus directories
  - Copies slash commands to ~/.claude/commands/
  - Installs PyYAML if missing (handles PEP 668)
  - Registers UserPromptSubmit hook in ~/.claude/settings.json

Options:
  --dry-run, -n    Print what would happen without changing anything.
  --help, -h       This help.
USAGE
      exit 0
      ;;
  esac
done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CLAUDE_HOME="$HOME/.claude"
EXP_HOME="$CLAUDE_HOME/experience"
COMMANDS_DIR="$CLAUDE_HOME/commands"
SETTINGS_FILE="$CLAUDE_HOME/settings.json"
HOOK_PATH="$SCRIPT_DIR/hooks/claude-code.sh"
LEGACY_HOOK_PATH="$SCRIPT_DIR/hooks/pre-prompt.sh"   # pre-v0.1.0 name; cleaned up below if present

# Logger helpers — in dry-run, prefix every action with [dry-run] and skip execution
say()    { echo "$@"; }
do_or_say() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] would: $*"
  else
    eval "$@"
  fi
}

if [ "$DRY_RUN" -eq 1 ]; then
  say "🔍 experience-layer installer (DRY RUN — no changes will be applied)"
else
  say "🧠 Installing experience-layer..."
fi
say "   Skill dir: $SCRIPT_DIR"
say ""

# 1. Corpus directories
say "▸ Creating corpus directories at $EXP_HOME"
do_or_say "mkdir -p \"$EXP_HOME/global/power-automate\""
do_or_say "mkdir -p \"$EXP_HOME/global/solana\""
do_or_say "mkdir -p \"$EXP_HOME/global/frontend\""
do_or_say "mkdir -p \"$EXP_HOME/global/general\""
do_or_say "mkdir -p \"$EXP_HOME/logs\""

# 2. Slash commands
say "▸ Installing slash commands to $COMMANDS_DIR"
do_or_say "mkdir -p \"$COMMANDS_DIR\""
for cmd in "$SCRIPT_DIR/commands"/exp-*.md; do
  if [ -f "$cmd" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "[dry-run] would: cp $(basename "$cmd") -> $COMMANDS_DIR/"
    else
      cp "$cmd" "$COMMANDS_DIR/"
      echo "    $(basename "$cmd")"
    fi
  fi
done

# 3. Python + PyYAML
say "▸ Checking Python 3 and PyYAML"
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ❌ python3 not found. Install Python 3 first (e.g. brew install python)."
  exit 1
fi
if ! python3 -c "import yaml" 2>/dev/null; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] would: install PyYAML via pip --user (with PEP 668 fallback)"
  else
    echo "  ▸ Installing PyYAML (user install)"
    # Modern Python on macOS (Homebrew, system) is "externally managed" (PEP 668).
    # Try the safe path first, fall back to --break-system-packages with --user.
    if python3 -m pip install --user --quiet pyyaml 2>/dev/null; then
      :
    elif python3 -m pip install --user --break-system-packages --quiet pyyaml 2>/dev/null; then
      :
    elif command -v pipx >/dev/null 2>&1 && pipx install pyyaml 2>/dev/null; then
      :
    else
      echo "  ⚠️  Couldn't install PyYAML automatically."
      echo "     Try one of:"
      echo "       python3 -m pip install --user --break-system-packages pyyaml"
      echo "       brew install pipx && pipx install pyyaml"
      exit 1
    fi
  fi
fi

# 4. Make scripts executable
say "▸ Making scripts executable"
do_or_say "chmod +x \"$HOOK_PATH\""

# 5. Register hook in settings.json
say "▸ Registering UserPromptSubmit hook in $SETTINGS_FILE"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] would: ensure $SETTINGS_FILE exists, back it up, then add hook entry pointing at $HOOK_PATH"
  echo "[dry-run] would: remove any pre-v0.1.0 entries pointing at $LEGACY_HOOK_PATH"
  echo ""
  echo "✅ dry-run complete. Re-run without --dry-run to apply."
  exit 0
fi

if [ ! -f "$SETTINGS_FILE" ]; then
  echo '{}' > "$SETTINGS_FILE"
fi

cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup-$(date +%Y%m%d-%H%M%S)"

python3 - <<EOF
import json
from pathlib import Path

p = Path("$SETTINGS_FILE")
raw = p.read_text().strip() or "{}"
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    print(f"  ❌ settings.json is not valid JSON: {e}")
    print(f"  Backup created. Fix the JSON manually and re-run install.sh.")
    raise SystemExit(1)

hooks = data.setdefault("hooks", {})
ups = hooks.setdefault("UserPromptSubmit", [])

cmd = "$HOOK_PATH"
legacy_cmd = "$LEGACY_HOOK_PATH"


def is_target(value, target):
    return isinstance(value, str) and value == target


def entry_matches(entry, target):
    if not isinstance(entry, dict):
        return False
    if is_target(entry.get("command"), target):
        return True
    nested = entry.get("hooks", [])
    if isinstance(nested, list):
        for h in nested:
            if isinstance(h, dict) and is_target(h.get("command"), target):
                return True
    return False


# Cleanup: drop pre-v0.1.0 entries pointing at the renamed hook
removed_legacy = 0
new_ups = []
for entry in ups:
    if entry_matches(entry, legacy_cmd):
        removed_legacy += 1
        continue
    new_ups.append(entry)
ups[:] = new_ups
if removed_legacy:
    print(f"  ▸ Removed {removed_legacy} legacy entry/entries (hooks/pre-prompt.sh → hooks/claude-code.sh)")

already = any(entry_matches(entry, cmd) for entry in ups)

if not already:
    # Use the documented Claude Code hook structure
    ups.append({
        "matcher": "*",
        "hooks": [
            {"type": "command", "command": cmd}
        ]
    })

p.write_text(json.dumps(data, indent=2) + "\n")
print("  ✅ Hook registered" if not already else "  ✅ Hook already registered (no change)")
EOF

echo ""
echo "✅ experience-layer installed."
echo ""
echo "Next steps:"
echo "  1. Restart Claude Code (or open a new session) so the hook loads."
echo "  2. Run: /exp-onboard  ← seeds your first 5 patterns (~15 min)"
echo "  3. Use Claude Code normally. Warnings inject automatically when relevant."
echo ""
echo "Kill switches:"
echo "  • Per project: touch .experience-disabled  (in project root)"
echo "  • Global:      export EXPERIENCE_LAYER=off"
echo ""
echo "Status:        /exp-status"
echo "Tune:          /exp-tune"
echo "Capture new:   /exp-capture"
echo ""
