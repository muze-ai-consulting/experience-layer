# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-04-26

Patch release addressing the P0/P1 items from the second round of external review. All non-breaking. The headline change is **observability**: silently-rejected patterns are now visible via `lib/diag.py` and `/exp-status`, and the nudge writes per-fire logs so its signal can be measured instead of just claimed.

### Added
- **`lib/diag.py`** — corpus inspection script that walks both global and project corpora, classifying every `*.md` as either loaded or rejected with a stable reason code (`missing_provenance`, `malformed_yaml`, `archived`, `no_frontmatter`, `incomplete_frontmatter`, `frontmatter_not_dict`, `provenance_not_dict`, `read_error`). Run directly or via `--json` for tooling. Wired into `/exp-status` so silent failures are no longer invisible.
- **`lib/retrieve.py::_load_pattern_diagnostic`** — returns `(pattern, reason)` so `diag.py` can report rejections per file. The hot-path `_load_pattern` is preserved (still silent at load — fail-open guarantee untouched).
- **`lib/nudge.py` logging** — appends one JSONL entry per fire to `~/.claude/experience/logs/nudges.jsonl`. Stores `prompt_hash` (sha256[:16]) and `context_size_in`, never the prompt text itself (privacy guarantee tested).
- **`/exp-tune` nudge section** — surfaces fire count, time range, and a rough conversion-to-capture heuristic so the user can judge whether the nudge is producing signal or just noise.
- **`install.sh --dry-run`** — prints every action without applying it. Lets you see exactly what the installer would touch (`~/.claude/experience/`, `~/.claude/commands/`, `~/.claude/settings.json`) before it runs.
- **9 new tests** — 6 for `_load_pattern_diagnostic` (one per rejection code), 3 for nudge logging (fire writes, no-fire silent, prompt text never in log).

### Changed
- **README compatibility section** — qualified the "30-50 lines" portability claim. Now explicit that the line count is for the stdin/stdout glue only; lifecycle, error handling, timeout semantics, and agent UX are not free.
- **GitHub repo metadata** — description, homepage URL, and 8 topics for discoverability (`claude-code`, `agent-skills`, `llm-tooling`, `prompt-engineering`, `context-engineering`, `markdown-corpus`, `anti-patterns`, `developer-tools`).

### Why these and not others
The external review had a longer P0/P1/P2 list. We deliberately skipped:
- **Splitting `lib/retrieve.py` into modules** — 300 lines, single concern, no second client of the interfaces yet. Refactoring for "modularity" without a real driver is bureaucracy.
- **Embedding-based semantic match** — V3 work. No data yet showing recall collapses on lexical matching.
- **Larger installer hardening** — `--dry-run` covers the user-visibility complaint; further hardening needs a concrete attack model.
- **Re-evaluation with non-curated corpus** — impossible to do via commit. That validation comes from real usage; the new nudges/saves/false-positives logs are exactly the instrumentation needed to produce it over the next 2 weeks.

## [0.1.0] - 2026-04-26

First tagged release. The initial commit (8476b53) shipped the core skill; this tag adds the test suite, benchmark harness, adapter pattern, and an honest README pass.

### Added
- **Test suite** (`tests/`) — 48 unit + integration tests covering pattern loading, kill switches, scoring, domain detection, retry-signal detection, and end-to-end retrieve subprocess. Stdlib only (`unittest`), no new dependencies. Run: `python3 -m unittest discover -s tests`.
- **Benchmark harness** (`benchmark/run.py`) — reproducible precision/recall/F1 over 20 hand-labeled prompts in `benchmark/eval.json` plus timing distribution (mean/p50/p95/p99) over N subprocess invocations. Outputs `benchmark/results.md` and `benchmark/results.json`.
- **Adapter pattern** — hook renamed to `hooks/claude-code.sh` with a contract documented in `hooks/README.md` so other agents (Cursor, Aider, Cline, etc.) can be ported by writing a 30-50 line bash/Python adapter. The core libs in `lib/` are now agent-agnostic.
- **`EXPERIENCE_LAYER_HOME` env var** — overrides the corpus root (default `~/.claude`) without touching `HOME`. Used by the test suite and benchmark; available to users for multi-corpus setups.

### Changed
- **README** — replaced "Design Principles" (abstract) with "Design Choices" (concrete tradeoffs explaining what each choice closes off and why). Replaced "Performance" hand-wave with measured benchmark results. Replaced "Compatibility" agnostic-claim with honest acknowledgement that the only existing adapter is for Claude Code, plus a pointer to the contract doc for porting.
- **`hooks/pre-prompt.sh` → `hooks/claude-code.sh`** — install.sh cleans up legacy entries from existing `~/.claude/settings.json` registrations.
- **`nudge.py`** — relaxed the English "failed" pattern (was `(that|this) failed`, now `\bfailed\b`); added `\bisn't working\b`. Catches more real retry signals at the cost of slightly higher false-positive risk on phrases like "feature failed to launch".

### Fixed
- **PEP 668 install** — `install.sh` now tries `pip install --user`, falls back to `--break-system-packages`, then `pipx`. Modern macOS Python installs work out of the box.
- **macOS hook latency** — `hooks/claude-code.sh` detects whether `timeout` or `gtimeout` is available and runs the libs without external timeout if neither is present, instead of silently failing on macOS where `timeout` ships only with GNU coreutils.

### Known limitations
- Matching is keyword + regex only. Paraphrased prompts that don't share lexical structure with the trigger keywords will miss. Embedding-based semantic match is on the V2/V3 roadmap.
- The 1.00/1.00/1.00 benchmark numbers come from a curated eval. Real-world precision/recall require real usage and the `/exp-saved` + `/exp-falsepositive` feedback loop.
- Only Claude Code is supported today. Adapter for other agents requires writing a new `hooks/<agent>.sh`.

[Unreleased]: https://github.com/muze-ai-consulting/experience-layer/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/muze-ai-consulting/experience-layer/releases/tag/v0.1.1
[0.1.0]: https://github.com/muze-ai-consulting/experience-layer/releases/tag/v0.1.0
