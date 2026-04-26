# Injection Format — how warnings render

The hook outputs plain markdown to stdout. For `UserPromptSubmit`, Claude Code prepends this output to the user's prompt as additional context. The format below balances signal density with readability.

## Standard format

```
⚠️ **experience-layer warnings** (top N matches)

🔴 **[HIGH]** <pattern title>  `id=<pattern-id>`
   Trigger: `<keyword>`, `/<regex>/`
   Rule: <fix text, truncated to ~400 chars>
   Source: <url or session_id>  (last seen <date>)

🟡 **[MED]** <pattern title>  `id=<pattern-id>`
   Trigger: `<keyword>`
   Rule: <fix text>
   Source: <url>  (last seen <date>)

⚪ **[LOW]** <pattern title>  `id=<pattern-id>`
   Trigger: `<keyword>`
   Rule: <fix text>
   Source: <session_id>  (last seen <date>)

_If a warning saved you: `/exp-saved <id>`. If it didn't apply: `/exp-falsepositive <id>`._
```

## Severity icons

| Severity | Icon | Color (visual cue) |
|---|---|---|
| `high` | 🔴 | red |
| `med`  | 🟡 | yellow |
| `low`  | ⚪ | white/light |

## Field rationale

- **`id=...`**: visible so user can quickly run `/exp-saved <id>` or `/exp-falsepositive <id>` without copy-paste gymnastics.
- **Trigger**: shows what fired the match — useful for catching false positives at a glance.
- **Rule**: the actionable guidance, truncated. Full rule lives in the pattern file body.
- **Source**: provenance. Always present (since loader rejects no-provenance patterns).
- **Last seen**: helps the user judge whether the pattern is fresh or stale.

## Why this format

- **Density first**: every line carries information. No filler.
- **Severity icon early**: visual scan-ability — user sees red icons and pays attention.
- **ID at line end**: easy to copy when needed, doesn't compete with the title for attention.
- **Markdown**: renders well both in Claude Code's terminal and in the model's reading.
- **Trailing affordance line**: reminds the user they can mark saves/FPs without making them learn the commands separately.

## Modifying the format

Edit `_render()` in `lib/retrieve.py`. The function takes `top: list[(score, pattern, fired_triggers)]` and returns a single string. Test changes via:

```bash
echo '{"prompt":"<test>"}' | python3 ~/.claude/skills/experience-layer/lib/retrieve.py
```

Common modifications:
- **Shorter rule cap**: change `if len(fix) > 400` in `_render()` to a smaller number for terser output
- **Add timestamp**: prepend the current ISO time
- **Group by severity**: sort top matches by severity tier first, score within tier
- **Plain text mode**: strip emoji + markdown for environments where they render badly

## What NOT to do

- **Don't dump full pattern bodies**: the inline warning is for the model to read at the moment of decision. Long bodies waste context. The model can read the source file if it needs more.
- **Don't add tone language** ("be careful!", "watch out!"): the model gets it. Plain rules work better than dramatic framing.
- **Don't omit the ID**: without it, `/exp-saved` requires the user to grep their logs.
- **Don't omit provenance**: if a warning has no source, the user can't trust it.
