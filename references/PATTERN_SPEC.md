# Pattern Spec — frontmatter contract

Every pattern is a markdown file with YAML frontmatter + body. The loader (`lib/retrieve.py`) rejects patterns that don't satisfy the contract below — silently — so a malformed pattern won't break Claude's session, it just won't trigger.

## Filename
`<domain>-YYYY-MM-DD-<short-slug>.md` — chronological + readable. The `id` in the frontmatter is the canonical reference; filename is for humans.

## Required fields

| Field | Type | Notes |
|---|---|---|
| `id` | string | Globally unique. Convention: `<domain>-YYYY-MM-DD-<slug>` |
| `name` | string | Human-readable, ~10 words, describes the trap |
| `severity` | enum | `low` \| `med` \| `high` |
| `domain` | string | `power-automate`, `solana`, `frontend`, `general`, or any custom name |
| `triggers` | object | At least one of `keywords` or `regex` non-empty |
| `triggers.keywords` | list[string] | Substring match, case-insensitive |
| `triggers.regex` | list[string] | Python `re` syntax, case-insensitive |
| `fix` | string (multiline) | Actionable guidance |
| `last_seen` | string (ISO date) | YYYY-MM-DD |
| `provenance` | object | At least one of `url` or `session_id` REQUIRED |

## Provenance (anti-fabrication)

```yaml
provenance:
  url: "https://learn.microsoft.com/..."   # public source
  session_id: "claude-code-2026-04-12-myproject"  # internal session id
  commit: "abc1234"                                # repo commit if relevant
```

Rule: **at least one of `url` or `session_id` must be non-null/non-empty**. If both are missing, `retrieve.py` rejects the pattern at load time. This blocks accidental fabrication where someone (or a future automated capture step) writes a pattern with no real source.

Rationale: per *Context Injection Attacks on LLMs* (arXiv:2405.20234), injecting unverifiable "experience" into a model's context is functionally identical to a context-injection attack. Provenance is the defensive boundary.

## Optional fields (auto-managed)

| Field | Type | Default | Notes |
|---|---|---|---|
| `review_status` | enum | `pending` | `pending` \| `validated` \| `archived`. Archived patterns are skipped at load. |
| `hits` | int | 0 | Incremented by `/exp-saved` |
| `last_save_at` | string (ISO date) | null | Set by `/exp-saved` |
| `false_positives` | int | 0 | Incremented by `/exp-falsepositive` |

## Body structure

After the closing `---`, write a markdown body. Recommended sections:

```markdown
# <pattern title>

## Context
What happened, when, where. 2-4 lines.

## Why generic warnings miss this
Why an LLM wouldn't naturally know this — what's the LLM's default mistake here?
This section is what makes the pattern *more useful than the model's prior*.

## What to do instead
Step-by-step or bullet list. Concrete actions. Numbers, thresholds, configs.

## Related patterns
List related pattern IDs if any (helps cross-link the corpus).
```

## Trigger design tips

**Good triggers** are specific enough that they only fire on the actual scenario:
- ✅ `"flow recurrence every minute"` — matches the specific pattern
- ✅ regex `"Power Automate.*every.*minute"` — narrow
- ❌ `"flow"` — too broad, matches everything mentioning flows
- ❌ `"error"` — matches every failure prompt

Keyword count: 3-5 keywords + 1-2 regex is a healthy starting point. Too many → false positives; too few → silence.

## Severity guide

| Severity | When | Example |
|---|---|---|
| `high` | Silent failures, data loss, security, expensive mistakes (cost or time >2h) | Flow throttle silently skips runs |
| `med` | Visible bugs that waste 30+ min to diagnose | Token expires mid-flow, fix requires manual restart |
| `low` | Gotchas that take <15 min once you know them | Default attachment MIME wrong, easy fix |

Severity affects the `severity_weight` multiplier in ranking — high patterns win ties against low ones.

## Full example

See [`examples/power-automate-flow-trigger-rate-limit.md`](../examples/power-automate-flow-trigger-rate-limit.md) for a complete, well-formed pattern. Other domains in `examples/`:

- `examples/react-useeffect-infinite-loop.md` — frontend, medium severity
- `examples/solana-jito-bundle-tip-placement.md` — Solana, high severity

The shape in summary:

```markdown
---
id: <domain>-YYYY-MM-DD-<slug>
name: <one-line, ~10 words>
severity: low | med | high
domain: <name>
triggers:
  keywords: [...]
  regex: [...]
fix: |
  <multiline, actionable: thresholds, configs, steps>
last_seen: YYYY-MM-DD
provenance:
  url: <public source URL — preferred>
  session_id: <internal id when no public source>
  commit: <SHA if relevant>
review_status: pending | validated | archived
hits: 0
last_save_at: null
false_positives: 0
---

# <pattern title>

## Context
## Why generic warnings miss this
## What to do instead
## Related patterns
```
