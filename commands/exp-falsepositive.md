---
description: Mark a recently-injected experience-layer warning as a false positive (the warning fired but didn't apply). Reduces the pattern's score and offers to archive if it's noisy.
---

# /exp-falsepositive

The warning fired but didn't apply to this task. Reduce its match strength so it stops creating noise.

## What to do

### 1. Resolve the pattern ID
- If user provided one (e.g. `/exp-falsepositive solana-2025-11-20-jito-bundle-tip`), use it.
- Otherwise, read recent injections from `~/.claude/experience/logs/injections.jsonl` and ask the user which one was wrong.

### 2. Find the pattern file
Search global → project. If not found, tell the user.

### 3. Update the frontmatter
- Increment `false_positives` by 1.
- Optionally ask the user *why* it didn't apply — useful for refining triggers.

### 4. Append to log
```
~/.claude/experience/logs/false_positives.jsonl
```
Entry:
```json
{"ts": "<ISO>", "pattern_id": "<id>", "action": "false_positive", "reason": "<user input or null>"}
```

### 5. Auto-archive check
If the pattern now has `false_positives >= 3` AND `hits == 0`, the pattern has signaled noise repeatedly without ever saving anyone. Ask:

> "Este patrón disparó 3+ veces sin saves. ¿Lo archivo (`review_status: archived` → `retrieve.py` lo ignora a partir de ahora)? [y/N]"

On `y`: set `review_status: archived` in the frontmatter. Confirm with the path so user can re-enable manually if needed.

### 6. Confirm
> "✅ Marked `<id>` as false positive (FP=N, hits=N). [If archived: Pattern archived — no longer injects.]"

## When to refine triggers instead of archiving

If the user explains *why* it was a false positive in a way that suggests the trigger is too broad, offer:

> "El trigger `<X>` parece muy amplio. ¿Lo cambio a `<Y>` para que solo dispare cuando <más específico>?"

This is more valuable than archiving — it preserves the lesson while killing the noise.
