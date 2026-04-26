---
description: Capture a new failure pattern from the last few turns of conversation. Auto-drafts the pattern using context, user approves/edits before saving to the experience-layer corpus.
---

# /exp-capture

The user just experienced a failure (or wants to log a lesson) and wants to add it to the experience-layer corpus so future tasks don't repeat it.

## What to do

### 1. Read the last 3-5 turns of the conversation
Identify:
- What was the user trying to do?
- What went wrong (or what surprised them)?
- What was the actual fix or correct approach?
- Which domain does this belong to? (`power-automate` / `solana` / `frontend` / `general` / project-specific)
- Is it specific to one project/repo or generally applicable across projects?

### 2. Auto-draft the pattern

Use the format from `~/.claude/skills/experience-layer/references/PATTERN_SPEC.md`. Severity guide:
- **high**: silent failures, data loss, security issues, expensive mistakes
- **med**: visible bugs that waste 30+ min to diagnose
- **low**: gotchas that take <15 min once you know them

Draft the full file content (frontmatter + body). Make triggers specific (not "error"). Make the fix actionable (not "be careful").

### 3. Show the draft to the user

Present the full markdown file. Ask:
> "Save this as drafted, edit something, or discard?"

If the user wants edits, apply them and re-confirm.

### 4. Determine save location

- **Project-specific** (refers to a single repo, names a specific service, mentions specific data) → `<git-root>/.claude/experience/<id>.md`
- **Global** → `~/.claude/experience/global/<domain>/<id>.md`

If the domain directory doesn't exist under global, create it.

### 5. Save and confirm

Write the file. Confirm:
> "Pattern saved to `<full-path>`. Will trigger on prompts matching: `<list of triggers>`. Run `/exp-status` to verify it loaded."

## Provenance rules (CRITICAL)

A pattern with neither `provenance.url` nor `provenance.session_id` will be **rejected at load time** by `retrieve.py`. This is anti-fabrication insurance (per arXiv:2405.20234, *Context Injection Attacks on LLMs*).

When you don't have a public URL:
- Use `session_id: claude-code-YYYY-MM-DD-<short-context>` — that's enough to satisfy provenance.
- If there's a relevant commit in the current repo, capture the SHA via `git rev-parse HEAD` and put it in `commit`.
- If the user remembers a Stack Overflow / GitHub Issue / docs page, ask for the URL.

## Common drafting mistakes to avoid

- **Triggers too generic**: "error" matches every failure prompt. Use phrases that uniquely indicate this scenario. Bad: `"error"`. Good: `"flow trigger every minute"`.
- **Generic fix text**: "Be careful with X" doesn't help future-Claude. Bad: "Be careful with rate limits". Good: "If recurrence ≤ 1 min, calls/day = 1440 × actions; with SharePoint connector at 60/min, daily user limit is ~6000. Use ≥5 min unless event-driven."
- **Missing why**: include "## Why generic warnings miss this" — this section is what makes the pattern *more useful than the LLM's default knowledge*.
- **Forgetting `last_seen`**: set it to today's date.

## Domain hints

- Project-specific patterns (named clients, repos, services) → save under `<git-root>/.claude/experience/`
- General-purpose patterns that any project might trigger → `~/.claude/experience/global/general/`
- Tooling-specific (Power Automate, Solana, frontend, etc.) → `~/.claude/experience/global/<tool>/`
