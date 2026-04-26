# experience-layer

> Scar tissue for LLMs. Inject your past failures into the model's context, before generation.

LLMs have read more than any of us ever will. They still ship the same bugs over and over. The reason isn't ignorance — it's that they have no scar tissue. A senior engineer doesn't outperform a fresh graduate because they read more papers; they outperform because they remember the specific way a thing broke and reach for the fix automatically.

This project builds that layer for an LLM.

It is **not** another memory plugin. It is **not** a rules file. It is a structured corpus of past failures, retrieved at prompt time, ranked by severity × recency × match strength, and injected as warnings *before* the model generates a response. Every entry has a verifiable source. No source → not injected. The corpus is local-only.

```
[your prompt]
     ↓
UserPromptSubmit hook (~70ms)
     ↓
match against corpus → top 3 patterns
     ↓
inject as structured warnings
     ↓
[model generates with the warnings already in context]
```

## Quick start

Built for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). Works with any setup that supports `UserPromptSubmit` hooks.

```bash
git clone https://github.com/muze-ai-consulting/experience-layer ~/.claude/skills/experience-layer
bash ~/.claude/skills/experience-layer/install.sh
```

The installer is idempotent: it creates the corpus directories, registers the hook in `~/.claude/settings.json` (with a backup), copies the slash commands into `~/.claude/commands/`, and installs PyYAML if it's missing.

Restart Claude Code, then run:

```
/exp-onboard
```

A 15-minute interactive wizard. Pick a domain, describe five things that have already burned you, the LLM auto-drafts the patterns, you approve, they're saved. From that moment on, prompts that look anything like those scenarios pull the warnings into context before Claude responds.

## What you actually see

When a pattern fires, the warning is prepended to the model's view of your prompt:

```
⚠️ experience-layer warnings (top 1 match)

🔴 [HIGH] Power Automate flow trigger fires silently under throttle  id=pa-2026-02-03-rate-limit
   Trigger: `flow trigger`, `every minute`, `/Power Automate.*every.*minute/`
   Rule: Per-user limit ~6000 calls/day; per-connector throttle 60/min on
   SharePoint. Triggers at 1-min recurrence silently throttle and skip
   executions WITHOUT erroring.
   - Polling: 5-15 min minimum unless event-driven
   - Event-driven: webhook triggers don't count against polling limits
   - Always include "Get past time" + dedup so missed runs don't lose data
   Source: https://learn.microsoft.com/.../api-request-limits-allocations  (last seen 2026-04-18)

If a warning saved you: /exp-saved <id>. If it didn't apply: /exp-falsepositive <id>.
```

The model sees this. You see this. If it was useful, `/exp-saved <id>` reinforces the pattern. If it fired on the wrong scenario, `/exp-falsepositive <id>` reduces its weight.

## Pattern format

Every pattern is one markdown file. Frontmatter is the contract:

```markdown
---
id: pa-2026-02-03-rate-limit
name: Power Automate flow trigger fires silently under throttle
severity: high                    # low | med | high
domain: power-automate
triggers:
  keywords: ["flow trigger", "every minute", "recurrence"]
  regex: ["Power Automate.*every.*minute"]
fix: |
  Per-user limit ~6000 calls/day; per-connector throttle 60/min on SharePoint.
  Triggers at 1-minute recurrence silently throttle and skip executions
  WITHOUT erroring.
  - Polling: 5-15 min minimum unless event-driven
  - Event-driven: webhook triggers don't count against polling limits
  - Always include "Get past time" + dedup so missed runs don't lose data
last_seen: 2026-04-18
provenance:
  url: https://learn.microsoft.com/en-us/power-platform/admin/api-request-limits-allocations
  session_id: null
  commit: null
review_status: validated
hits: 4
last_save_at: 2026-04-12
false_positives: 0
---

# Body: contexto, why generic warnings miss this, what to do instead, related patterns
```

`provenance` is mandatory. At least one of `url` or `session_id` must be non-empty, or the pattern is silently rejected at load. This is the defensive boundary — see *On provenance* below.

The full spec is in [`references/PATTERN_SPEC.md`](references/PATTERN_SPEC.md). Examples in [`examples/`](examples/).

## Architecture

```
experience-layer/
├── SKILL.md                 # Anthropic Skill metadata + activation logic
├── install.sh               # idempotent installer
├── hooks/
│   └── pre-prompt.sh        # UserPromptSubmit hook, fail-open
├── lib/
│   ├── retrieve.py          # corpus loader + ranker
│   └── nudge.py             # passive retry-signal detector
├── commands/                # six slash commands (see below)
├── references/              # PATTERN_SPEC, RETRIEVAL, INJECTION_FORMAT
└── examples/                # sample patterns to copy and adapt
```

The corpus lives outside the repo so your patterns can be private:

```
~/.claude/experience/
├── global/<domain>/*.md     # cross-project patterns
└── logs/                    # injections, saves, false-positives (JSONL)

<git-root>/.claude/experience/*.md   # project-scoped patterns
```

## Slash commands

| Command | What it does |
|---|---|
| `/exp-onboard` | 15-min wizard. Five seed patterns from one domain. |
| `/exp-capture` | LLM auto-drafts a pattern from the last N turns. You approve, edit, or discard. |
| `/exp-saved <id>` | Mark a recently-injected warning as having prevented a bug. Increments `hits`. |
| `/exp-falsepositive <id>` | Pattern fired but didn't apply. Reduces score; offers to archive after 3 FPs with no saves. |
| `/exp-tune` | Review the last 7 days of logs. Surfaces noisy patterns and proposes specific edits. |
| `/exp-status` | Corpus size, recent activity, kill-switch state. |

## Kill switches

The hook checks three independent off-switches before doing anything else, so a noisy or buggy corpus can be silenced without uninstalling:

```bash
# Per project (a single-line file, no contents needed)
touch <project-root>/.experience-disabled

# Global (current shell)
export EXPERIENCE_LAYER=off

# Per session
/exp-tune off
```

The no-op path runs in under 50ms.

## Retrieval

Per prompt:

1. Hook reads JSON from stdin (`{prompt, ...}`)
2. Resolves project root: `git rev-parse` → `cwd` fallback
3. Detects candidate domain(s) by keyword match
4. Loads patterns from `global/<domain>/` ∪ `<project>/.claude/experience/`
5. Rejects: missing provenance, malformed YAML, `review_status: archived`
6. Scores each: `severity_weight × recency_factor × match_strength × fp_penalty`
7. Filters by `MIN_SCORE`, sorts descending, takes top-N
8. Renders structured warnings to stdout
9. Appends one line to `logs/injections.jsonl`

Tunables are constants at the top of [`lib/retrieve.py`](lib/retrieve.py). Edit them; the hook re-runs Python on every prompt so changes apply immediately.

Full spec: [`references/RETRIEVAL.md`](references/RETRIEVAL.md).

## On provenance

Injecting un-sourced "experience" into a model's context is functionally identical to a context-injection attack ([arXiv:2405.20234](https://arxiv.org/abs/2405.20234)). A pattern with no `url` and no `session_id` is fabrication risk: nobody can verify the lesson, and the model will treat it as authoritative anyway.

So: no provenance, not injected. If you don't have a public URL, use a `session_id` you can trace back. If you don't even have that, the lesson isn't ready to be a pattern yet.

This sounds bureaucratic for what's essentially a personal corpus. It is not. The whole value of the layer is that the model treats it as ground truth. That privilege earns its keep with a verifiable source.

## On the nudge

In addition to the corpus retrieval, a tiny secondary script (`lib/nudge.py`) scans the prompt for retry / failure signals — *"that didn't work"*, *"intentemos otra vez"*, *"still broken"*, etc., bilingual — and if it sees one, suggests `/exp-capture`. Cheap to run, easy to disable, surprisingly effective at converting frustration into corpus.

## Design principles

1. **Fail-open.** The hook never blocks generation. Any error → silent skip, never a broken session.
2. **Provenance or it doesn't load.** No source = not injected.
3. **Structured rules, not generic advice.** "Be careful with X" is not a fix; thresholds, configs, and steps are.
4. **Domain-scoped, not blanket.** A Solana pattern shouldn't fire on a Power Automate prompt.
5. **Local first.** Patterns can hold proprietary context. Corpus stays on disk, never leaves the machine.
6. **Tunable, not magic.** Severity weights, recency decay, match thresholds are constants. Edit them.

## How it differs from adjacent work

|                                                         | Static rules<br/>(CLAUDE.md, .cursorrules) | Generic memory<br/>(mem0, MemGPT) | Reflexion<br/>Self-Refine | **experience-layer** |
|---------------------------------------------------------|:---:|:---:|:---:|:---:|
| Cross-session                                           | ✓ | ✓ | ✗ | ✓ |
| Failure-specialized                                     | ✗ | ✗ | ✓ | ✓ |
| Pre-generation injection                                | ✓ | partial | ✗ (post-hoc) | ✓ |
| Severity / recency scoring                              | ✗ | ✗ | ✗ | ✓ |
| Provenance enforced                                     | ✗ | ✗ | ✗ | ✓ |
| Auto-growing                                            | ✗ | ✓ | per-session | semi (LLM-assisted capture) |
| Local only / no external service                        | ✓ | ✗ | ✓ | ✓ |

## Performance

- Hard timeout in hook: 2s for retrieval, 1s for nudge (where `timeout`/`gtimeout` is available)
- Soft target: <500ms total
- Measured on a small corpus: ~70ms

If you're on macOS and want hard timeouts, install GNU coreutils: `brew install coreutils`. Without it, the hook still works — bounded by the scripts' own behavior plus the fail-open trap.

## Status

V1 ships:

- [x] Cross-session corpus, dual-layer (global + project-scoped)
- [x] Keyword + regex matching
- [x] Severity × recency × match-strength ranking
- [x] False-positive penalty + auto-archive after 3 FPs with no saves
- [x] Manual capture with LLM auto-draft
- [x] Passive bilingual retry-signal nudge
- [x] JSONL logs, kill switches, fail-open hook
- [x] Idempotent installer

Planned (V2+):

- [ ] Web-search pre-flight: detect library/API mentions, verify versions/breaking changes against the live web, cache with TTL, inject as warnings before generation
- [ ] Automated recency decay (cron/SessionStart)
- [ ] Embedding-based semantic match for when keyword/regex misses obvious matches
- [ ] LLM-driven auto-extraction of failures from the full transcript (not just the last turn)
- [ ] Cross-project mining: detect similar patterns across project corpora and propose promotion to global

## Compatibility

- **Claude Code** is the reference target. Hook integrates via `UserPromptSubmit` in `~/.claude/settings.json`.
- Other agents that expose a pre-prompt hook with stdin JSON should work with minor adjustments to the hook script.
- macOS, Linux. Windows not tested but should work with WSL.
- Python 3 + PyYAML are the only dependencies. Bash for the hook.

## Contributing

Contributions welcome — bug reports, new pattern examples, alternative ranking strategies, hook adaptations for other agents.

Especially welcome: **example patterns** for domains not yet covered. The strongest contribution is a pattern file you've actually used that prevented a bug, with a public URL or commit as provenance. Drop it in `examples/` with a PR.

## License

MIT. See [`LICENSE`](LICENSE).

---

*This is an experiment. The core hypothesis — that a structured, scored, provenance-enforced corpus of past failures injected before generation can meaningfully reduce iteration cost — is testable and may be wrong in your context. The kill switches exist so you can find out cheaply.*
