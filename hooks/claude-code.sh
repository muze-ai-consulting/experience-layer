#!/usr/bin/env bash
# experience-layer UserPromptSubmit hook
# CRITICAL: fail-open. Any error → silent exit 0. NEVER block generation.

# Disable strict-mode and trap errors so nothing here can fail loudly.
set +e
trap 'exit 0' ERR INT TERM PIPE

# Fast kill switches — bail before doing any work.
[ "${EXPERIENCE_LAYER:-on}" = "off" ] && exit 0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" 2>/dev/null)" 2>/dev/null && pwd 2>/dev/null)"
[ -z "$SCRIPT_DIR" ] && exit 0
LIB_DIR="$SCRIPT_DIR/../lib"

# Find project root (git → cwd) and check disable file.
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
[ -f "$PROJECT_ROOT/.experience-disabled" ] && exit 0

# Buffer stdin once (Claude Code sends a JSON event payload).
INPUT="$(cat 2>/dev/null)"
[ -z "$INPUT" ] && exit 0

# Detect a timeout command. macOS doesn't ship one; Homebrew coreutils provides `gtimeout`.
# If neither is available, run without an external timeout — the scripts have their own
# bounded behavior and the trap above keeps the hook fail-open.
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_CMD="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_CMD="gtimeout"
else
  TIMEOUT_CMD=""
fi

# Run retrieve and nudge. Both swallow their own errors.
if [ -n "$TIMEOUT_CMD" ]; then
  RETRIEVE_OUT="$(printf '%s' "$INPUT" | "$TIMEOUT_CMD" 2s python3 "$LIB_DIR/retrieve.py" 2>/dev/null)"
  NUDGE_OUT="$(printf '%s' "$INPUT" | "$TIMEOUT_CMD" 1s python3 "$LIB_DIR/nudge.py" 2>/dev/null)"
else
  RETRIEVE_OUT="$(printf '%s' "$INPUT" | python3 "$LIB_DIR/retrieve.py" 2>/dev/null)"
  NUDGE_OUT="$(printf '%s' "$INPUT" | python3 "$LIB_DIR/nudge.py" 2>/dev/null)"
fi

# Emit only if there's content. Plain stdout becomes additionalContext for UserPromptSubmit.
if [ -n "$RETRIEVE_OUT" ] || [ -n "$NUDGE_OUT" ]; then
  [ -n "$RETRIEVE_OUT" ] && printf '%s\n' "$RETRIEVE_OUT"
  if [ -n "$NUDGE_OUT" ]; then
    [ -n "$RETRIEVE_OUT" ] && printf '\n'
    printf '%s\n' "$NUDGE_OUT"
  fi
fi

exit 0
