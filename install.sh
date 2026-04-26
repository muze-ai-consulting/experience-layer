#!/usr/bin/env bash
# experience-layer installer — idempotent, safe to re-run
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CLAUDE_HOME="$HOME/.claude"
EXP_HOME="$CLAUDE_HOME/experience"
COMMANDS_DIR="$CLAUDE_HOME/commands"
SETTINGS_FILE="$CLAUDE_HOME/settings.json"
HOOK_PATH="$SCRIPT_DIR/hooks/claude-code.sh"
LEGACY_HOOK_PATH="$SCRIPT_DIR/hooks/pre-prompt.sh"   # pre-v0.1.0 name; cleaned up below if present

echo "🧠 Installing experience-layer..."
echo "   Skill dir: $SCRIPT_DIR"
echo ""

# 1. Corpus directories
echo "▸ Creating corpus directories at $EXP_HOME"
mkdir -p "$EXP_HOME/global/power-automate"
mkdir -p "$EXP_HOME/global/solana"
mkdir -p "$EXP_HOME/global/frontend"
mkdir -p "$EXP_HOME/global/general"
mkdir -p "$EXP_HOME/logs"

# 2. Slash commands
echo "▸ Installing slash commands to $COMMANDS_DIR"
mkdir -p "$COMMANDS_DIR"
for cmd in "$SCRIPT_DIR/commands"/exp-*.md; do
  if [ -f "$cmd" ]; then
    cp "$cmd" "$COMMANDS_DIR/"
    echo "    $(basename "$cmd")"
  fi
done

# 3. Python + PyYAML
echo "▸ Checking Python 3 and PyYAML"
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ❌ python3 not found. Install Python 3 first (e.g. brew install python)."
  exit 1
fi
if ! python3 -c "import yaml" 2>/dev/null; then
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

# 4. Make scripts executable
echo "▸ Making scripts executable"
chmod +x "$HOOK_PATH"

# 5. Register hook in settings.json
echo "▸ Registering UserPromptSubmit hook in $SETTINGS_FILE"
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
