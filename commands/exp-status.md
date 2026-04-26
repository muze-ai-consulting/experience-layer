---
description: Show experience-layer status — corpus size by domain, recent injection activity, kill switch state, and quick action prompts. Use to verify the skill is alive and working.
---

# /exp-status

Quick health check on experience-layer.

## What to do

Gather and display:

### 1. Corpus stats
- For each domain dir under `~/.claude/experience/global/`, count `*.md` files (only count those with valid provenance — load via Python and count surviving patterns)
- Project corpus: detect git root from cwd, count `*.md` in `<git-root>/.claude/experience/`

### 2. Activation state
- Hook registered? Read `~/.claude/settings.json`, check for entry pointing at `~/.claude/skills/experience-layer/hooks/pre-prompt.sh`
- Global kill switch: `EXPERIENCE_LAYER` env var (use `echo $EXPERIENCE_LAYER` via Bash)
- Project kill switch: `<git-root>/.experience-disabled` exists?
- Skill itself installed? `~/.claude/skills/experience-layer/SKILL.md` exists?

### 3. Recent activity (last 7 days)
- Tail `~/.claude/experience/logs/injections.jsonl`, count entries in window
- Top 3 patterns by injection count
- Saves count, FP count

### 4. Output

```
experience-layer status

Corpus
  Global:
    power-automate:  12 patterns
    solana:           5 patterns
    frontend:         8 patterns
    general:          2 patterns
    Total global:    27 patterns
  Project (<project-name or "no git root">):
    Patterns:         3

Activation
  Skill installed:           ✅
  Hook registered:           ✅ ~/.claude/skills/experience-layer/hooks/pre-prompt.sh
  Global kill switch:        on (EXPERIENCE_LAYER not set to off)
  Project kill switch:       on (no .experience-disabled)

Last 7 days
  Injections:       23
  Saves:            4
  False positives:  7
  Top:
    1. pa-2026-02-rate-limit        (8 inj)
    2. solana-2025-11-jito-bundle   (5 inj)
    3. frontend-2026-03-tailwind    (4 inj)

Useful actions
  /exp-onboard       → seed more patterns
  /exp-tune          → review signal vs noise
  /exp-capture       → add a new one
  /exp-saved <id>    → mark a warning as saved
  /exp-falsepositive <id>  → reduce a pattern's score
```

### 5. Edge cases

- **Skill not installed**: very early state. Suggest `bash ~/.claude/skills/experience-layer/install.sh`.
- **Hook not registered**: re-run install.sh.
- **Empty corpus**: "Corpus is empty. Run `/exp-onboard` to seed 5 patterns (~15 min)."
- **No logs yet**: "No activity recorded yet. The skill is ready but no prompt has triggered a pattern yet."
