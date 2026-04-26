# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/muze-ai-consulting/experience-layer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/muze-ai-consulting/experience-layer/releases/tag/v0.1.0
