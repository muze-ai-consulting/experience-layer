---
description: Mark a recently-injected experience-layer warning as having prevented a bug. Increments the pattern's hits counter and reinforces it in future ranking.
---

# /exp-saved

Record that a warning from experience-layer actually saved the user from repeating a mistake.

## What to do

### 1. Resolve the pattern ID
- If the user provided an ID (e.g. `/exp-saved pa-2026-02-03-flow-trigger-rate-limit`), use it directly.
- If no ID provided, read the last 50 lines of `~/.claude/experience/logs/injections.jsonl` and list the recent injections. Ask: "¿Cuál te salvó? <numbered list>"

### 2. Find the pattern file
Search in this order:
1. `~/.claude/experience/global/**/*.md` — match against `id:` in frontmatter
2. `<git-root>/.claude/experience/*.md`

If not found, tell the user the ID doesn't exist and ask if it was a typo.

### 3. Update the frontmatter
Increment `hits` by 1, set `last_save_at` to today's ISO date.

Use a simple sed-like edit (read file → modify YAML in place → write). Preserve everything else verbatim.

### 4. Append to log
```
~/.claude/experience/logs/saves.jsonl
```
Entry format:
```json
{"ts": "<ISO timestamp>", "pattern_id": "<id>", "action": "saved"}
```

### 5. Confirm
> "✅ Marked `<id>` as save (hits=N, last_save_at=YYYY-MM-DD). Pattern reinforced — it'll rank higher in future matches."

## Why hits matter

Patterns with high hit counts are more reliable signals. If the user ever runs `/exp-tune`, hit counts vs false-positive counts drive recommendations on what to keep, archive, or refine.
