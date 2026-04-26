---
description: Review experience-layer injection logs and propose threshold adjustments. Use after a week of usage to check signal-to-noise ratio. Also accepts "off" to disable for the current session.
---

# /exp-tune

Two modes: **off mode** (disable for session) and **analysis mode** (default).

## Off mode
If the argument is `off` (e.g. `/exp-tune off`), tell the user to run in their shell:
```bash
export EXPERIENCE_LAYER=off
```
Confirm: "Off for this session. To re-enable: `unset EXPERIENCE_LAYER` or open a new Claude Code session."

(Claude can't change the parent shell's env. The user has to set it themselves.)

## Analysis mode

### 1. Load logs (last 7 days)
Read these files; tolerate missing files:
- `~/.claude/experience/logs/injections.jsonl`
- `~/.claude/experience/logs/saves.jsonl`
- `~/.claude/experience/logs/false_positives.jsonl`

Filter to entries within the last 7 days (UTC).

### 2. Compute stats
- Total injections
- Unique patterns injected (distinct `pattern_id`)
- Saves count
- False positives count
- Per-pattern: injections / saves / false-positives, save rate, FP rate

### 3. Surface findings

For each pattern with ≥2 injections in the window:
- **Useful** (save rate ≥30%): keep, maybe duplicate to other domains
- **Noisy** (FP rate ≥40% AND save rate <20%): triggers too broad, propose tightening or archiving
- **Cold** (only injected once or twice): inconclusive, leave alone for now

### 4. Output format

```
experience-layer tune (last 7 days)

Total injections:    23
Saves:               4   (17%)
False positives:     7   (30%) — high
Active:              12 patterns

Top injected:
1. ✅ pa-2026-02-rate-limit            | 8 inj, 2 saves (25%), 1 FP — useful
2. ⚠️  solana-2025-11-jito-bundle-tip   | 5 inj, 1 save (20%), 3 FP (60%) — noisy
3. ❌ frontend-2026-03-tailwind-arbitrary | 4 inj, 0 saves, 2 FP — archive candidate

Recommendations:
- Pattern #2: regex `jito.*tip` is too broad. Suggestion: change to `jito.*bundle.*tip`
  so it only matches bundles, not simple swaps. Apply the change?
- Pattern #3: 4 inj, 0 saves in 7 days. Archive?
- Pattern #1: working well. Consider duplicating to similar domains if relevant.
```

### 5. Apply changes
If the user agrees to suggestions, edit the pattern files directly. Confirm each edit with the path.

## Edge cases
- If logs are empty / non-existent: "No logs yet (skill recently installed or disabled). Come back after a few days of real use."
- If <5 total injections in 7 days: "Too little activity for conclusions. Wait another week or keep adding patterns with `/exp-capture`."
