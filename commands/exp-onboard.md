---
description: Interactive 15-minute wizard that helps the user seed 5 starter patterns from one domain into the experience-layer corpus. Run this immediately after install.sh — without seed patterns, experience-layer has nothing to inject.
---

# /exp-onboard

First-run wizard. Without seed patterns the experience-layer is silent — the user gets zero value until the corpus has content. This guides them through creating 5 high-quality patterns in ~15 minutes.

## Goal
Five patterns saved, validated, and ready to fire. Then a quick smoke test so the user sees a real warning before ending.

## Flow

### Step 1 — Choose domain
Ask:
> "Which domain do you want to seed first? Suggestions: `power-automate` (flows, connectors), `solana` (bots, on-chain programs), `frontend` (React, Tailwind, Vite), `general` (cross-domain), or a custom name."

If custom, `mkdir ~/.claude/experience/global/<custom-name>/` afterwards.

### Step 2 — Brainstorm
Ask:
> "Think of 5 things that have already burned you in this domain. One sentence each. Silent failures, gotchas that cost you time, anti-patterns you discovered the hard way. 5 real and specific is better than 10 generic."

Wait for the user. If only 2-3 come, that's fine — start with what they have.

### Step 3 — Expand each item
For each item, ask three quick questions:

1. **What happened.** "What led you to discover it? 1-2 sentences — project, rough date, what failed."
2. **The fix.** "What will you do instead next time? Concrete action, not 'be careful'."
3. **Provenance.** "Is there a doc link, GitHub issue, Stack Overflow answer, or commit? If not, I'll generate a generic session_id."

Don't batch these — ask them one at a time per pattern. Much less overwhelming.

### Step 4 — Auto-draft and review
For each item, draft the full markdown using the format in `references/PATTERN_SPEC.md`. Estimate severity from cost/frequency in the user's description. Extract 3-5 keywords + 1-2 regex from the trigger phrases.

Show all 5 drafts together at the end:
> "Here are the 5 patterns assembled. Tell me if anything needs tweaking. Ready to save?"

### Step 5 — Save
On confirm, write each to `~/.claude/experience/global/<domain>/<id>.md`. Use IDs of the form `<domain>-YYYY-MM-DD-<slug>`.

### Step 6 — Smoke test
Ask the user for a sample prompt that should trigger one of the patterns. Run it through the retrieval engine in dry-run mode:

```bash
echo '{"prompt":"<sample>"}' | python3 ~/.claude/skills/experience-layer/lib/retrieve.py
```

Show the output. If it fires correctly:
> "The matcher works. The layer is alive. Next time you write something that hits these triggers, Claude will see the warning before responding."

If it doesn't fire, the triggers are too narrow. Suggest broadening them.

### Step 7 — Hand off
> "Done. Next steps:
> - Use Claude Code normally. When a pattern fires and saves you: `/exp-saved <id>`. When it fires wrong: `/exp-falsepositive <id>`.
> - Capture new patterns when something burns you: `/exp-capture`.
> - In 1-2 weeks, run `/exp-tune` to see signal vs noise and refine."

## Tips for the user during onboarding

- **Start with HIGH severity.** High-impact patterns give more value per unit of effort.
- **Specific triggers.** "flow recurrence every minute" >> "flow". The first matches only when applicable; the second generates noise.
- **The fix has to be actionable.** If the fix says "be careful", it doesn't work. It has to specify what to do — concretely, with numbers/thresholds/configs.
- **Always include provenance.** If genuinely no source exists, use `session_id: claude-code-onboarding-<date>` — but ideally link to real docs.
