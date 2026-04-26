---
description: Show experience-layer status — corpus size by domain, recent injection activity, kill switch state, and quick action prompts. Use to verify the skill is alive and working.
---

# /exp-status

Quick health check on experience-layer.

## What to do

Gather and display:

### 1. Corpus stats — via lib/diag.py

Run the inspection helper:

```bash
python3 ~/.claude/skills/experience-layer/lib/diag.py --json
```

This walks both global and project corpora, separating **loaded** (valid frontmatter + provenance + not archived) from **rejected** (with explicit reason codes: `missing_provenance`, `malformed_yaml`, `archived`, etc.). Use the JSON output to drive the report.

**This is the answer to a real complaint** about silent failures: patterns that look correct in your editor but never fire because of (e.g.) missing provenance now show up here with a stable reason code. No more invisible misses.

### 2. Activation state
- Hook registered? Read `~/.claude/settings.json`, check for entry pointing at `~/.claude/skills/experience-layer/hooks/claude-code.sh`
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

Corpus (via lib/diag.py)
  Loaded:   27 patterns
    global/power-automate:  12
    global/solana:           5
    global/frontend:         8
    global/general:          2
  Project (<project-name>): 3 patterns
  Rejected: 2 patterns (silent at load — surfaced here)
    [missing_provenance] global/solana/2025-09-old.md
        → Neither provenance.url nor provenance.session_id is set
    [archived] global/general/old-deprecated.md
        → review_status is archived (intentionally skipped)

Activation
  Skill installed:           ✅
  Hook registered:           ✅ ~/.claude/skills/experience-layer/hooks/claude-code.sh
  Global kill switch:        on (EXPERIENCE_LAYER not set to off)
  Project kill switch:       on (no .experience-disabled)

Last 7 days
  Injections:       23
  Saves:            4
  False positives:  7
  Nudges fired:     12
  Top patterns:
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

**Always include the rejected section if any patterns were rejected.** That's the whole point of running `diag.py` — to make silence visible.

### 5. Edge cases

- **Skill not installed**: very early state. Suggest `bash ~/.claude/skills/experience-layer/install.sh`.
- **Hook not registered**: re-run install.sh.
- **Empty corpus**: "Corpus is empty. Run `/exp-onboard` to seed 5 patterns (~15 min)."
- **No logs yet**: "No activity recorded yet. The skill is ready but no prompt has triggered a pattern yet."
