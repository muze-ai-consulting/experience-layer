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
│   ├── README.md            # adapter contract for porting to other agents
│   └── claude-code.sh       # Claude Code UserPromptSubmit adapter
├── lib/
│   ├── retrieve.py          # corpus loader + ranker (agent-agnostic)
│   └── nudge.py             # passive retry-signal detector (agent-agnostic)
├── commands/                # six slash commands (see below)
├── references/              # PATTERN_SPEC, RETRIEVAL, INJECTION_FORMAT
├── examples/                # sample patterns to copy and adapt
├── tests/                   # unittest suite (no external deps)
└── benchmark/               # precision/recall + timing harness
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

## Design choices

These are the deliberate tradeoffs. Each one closes a door — that's the point.

**Keyword + regex matching, not embeddings.** V1 uses substring keyword + Python `re` regex. This is fragile to paraphrase. It's also fast (no model, no vector store), deterministic, debuggable by reading the pattern file, and scales linearly with the corpus. Patterns describe failures whose signature is mostly lexical (library names, function names, error strings, configs), so the failure mode here is narrower than it sounds. Embedding-based semantic match is V3 — adopted only if benchmark recall actually drops on real usage.

**Frontmatter contract over schema validation.** Every pattern is a markdown file with YAML frontmatter. There's no schema validator that yells if you mistype a field. The loader silently rejects malformed patterns and moves on. This means a typo causes a silent miss instead of a failed install — bad for discoverability, good for fail-open. `/exp-status` and the test suite are how you catch typos.

**Provenance enforced at load, not at write.** A pattern with no `url` and no `session_id` is silently dropped at load time. We don't validate when you write the file (no "save error"); we just refuse to inject it. The reason: a pattern that looks correct in your editor but never fires is a louder signal than a pattern that refuses to save.

**Local-only, no daemon, no service.** The corpus is markdown on disk. There is no background process, no embedded database, no sync. Patterns can hold proprietary context safely; the cost is that there's no cross-machine sharing without you setting up your own sync (git is one option).

**Hook spawns Python per prompt.** Each prompt costs one Python interpreter startup (~25ms on macOS). We considered a long-lived daemon to amortize this; rejected because (a) startup is below the noise of LLM latency anyway, (b) a daemon adds an attack surface and a failure mode, (c) the simple model is much easier to reason about.

**Structured rules, not advice.** A pattern's `fix` field should contain thresholds, configs, and steps — not "be careful with X". "Be careful" doesn't help future-Claude any more than the model's prior; the value of the pattern is the *specific knowledge the model wouldn't have on its own*. This is on the human writing the pattern; nothing in the code enforces it.

**Domain-scoped, not blanket.** Patterns live under `global/<domain>/` and the loader only scans relevant domains for a given prompt. A Solana pattern shouldn't fire on a Power Automate prompt. The cost: a prompt that crosses domains might miss a relevant pattern; mitigated by the `general/` domain which is always scanned.

**Kill switches checked first.** Per-project file, env var, per-session env var. All checked before any corpus loading. The no-op path is under 50ms. We expect users to disable the layer per-project for sensitive work or noisy contexts; making that path cheap means people will actually use it instead of uninstalling.

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

## Benchmarks

Reproducible via [`benchmark/run.py`](benchmark/run.py). The eval set is 20 hand-labeled prompts in [`benchmark/eval.json`](benchmark/eval.json), running against the patterns in [`examples/`](examples/) (3 patterns covering Power Automate, React, Solana).

Latest run (`python3 benchmark/run.py --iterations 50`):

| metric | value |
|---|---|
| precision | 1.00 |
| recall | 1.00 |
| F1 | 1.00 |
| mean latency | 28.4 ms |
| p95 latency | 29.9 ms |
| p99 latency | 30.6 ms |

**Read this honestly.** The eval set is curated — 10 prompts designed to fire the patterns and 10 designed not to. Hitting 1.00 here means *the system does what it claims on a sample we picked*. Real-world precision/recall require real usage with patterns you didn't write the eval against. The synthetic benchmark catches regressions and tells you the wiring works; it does not prove the system is useful for your distribution. That's what `/exp-saved` and `/exp-falsepositive` are for.

The "adjacent" negatives (5/10 of the should-not-trigger cases) intentionally share keywords with the patterns without matching their actual scenarios — e.g. *"Solana wallet adapter integration"* shares the `solana` domain with the Jito pattern but no trigger keywords. These are the ones that test whether triggers are tight enough.

**Hard timeouts** in the hook: 2s for retrieve, 1s for nudge (where `timeout`/`gtimeout` is available). Without it, the hook runs without an external bound — the scripts have their own bounded behavior plus the fail-open trap. macOS users who want hard timeouts: `brew install coreutils`.

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

**Today this is a Claude Code skill.** The only adapter that exists is [`hooks/claude-code.sh`](hooks/claude-code.sh), which wires the core libs to Claude Code's `UserPromptSubmit` hook. The core (`lib/retrieve.py`, `lib/nudge.py`) is agent-agnostic — it reads JSON from stdin and writes markdown to stdout — but until someone writes an adapter for Cursor/Aider/Cline/Continue/etc., calling this project "agent-agnostic" would be vapor.

The contract for porting to another agent is documented in [`hooks/README.md`](hooks/README.md). The actual work is usually 30-50 lines of bash or Python — all the agent-specific concerns are isolated in the adapter.

If you write an adapter for another agent, please open a PR.

**Platforms**: macOS and Linux. Windows is untested; the bash adapter would need WSL or a PowerShell rewrite.

**Dependencies**: Python 3.9+ and PyYAML for the libs. Bash for the Claude Code adapter. Nothing else.

## Tests and benchmarks

Both have zero external dependencies (stdlib only):

```bash
# Unit + integration tests (~50 tests, 0.3s)
python3 -m unittest discover -s tests -v

# Precision/recall + timing benchmark
python3 benchmark/run.py
```

Benchmark output goes to [`benchmark/results.md`](benchmark/results.md) (human-readable) and `benchmark/results.json` (machine-readable, suitable for tracking over time).

## Contributing

Contributions welcome — bug reports, new pattern examples, alternative ranking strategies, hook adaptations for other agents.

Especially welcome: **example patterns** for domains not yet covered. The strongest contribution is a pattern file you've actually used that prevented a bug, with a public URL or commit as provenance. Drop it in `examples/` with a PR.

## License

MIT. See [`LICENSE`](LICENSE).

---

*This is an experiment. The core hypothesis — that a structured, scored, provenance-enforced corpus of past failures injected before generation can meaningfully reduce iteration cost — is testable and may be wrong in your context. The kill switches exist so you can find out cheaply.*
