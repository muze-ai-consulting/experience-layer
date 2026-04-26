# Contributing

Three kinds of contributions are useful here. In rough order of impact:

## 1. Example patterns

The single most valuable contribution is an `examples/<id>.md` file describing a real failure you've encountered, with verifiable provenance (a URL, a public commit, a public issue link). Patterns nobody actually uses are dead weight; patterns that prevented a real bug for someone are the whole point.

A good example pattern:

- Has a specific, scoped trigger (not "error" or "bug")
- Has an actionable fix with concrete numbers/configs/steps
- Has a `provenance.url` pointing to public docs, an issue, a Stack Overflow answer, a release note, or similar
- Includes a `## Why generic warnings miss this` section explaining what the model would naturally get wrong without the pattern

Open a PR. Title format: `add example: <domain> - <short-name>`.

## 2. Adapter for another agent

The reference target is Claude Code. The hook pattern (`UserPromptSubmit`-equivalent + JSON over stdin) generalizes to other agents. If you adapt the hook for Cursor, Aider, Cline, Continue, or anything else, send a PR with:

- A new file under `hooks/<agent-name>.sh` (or `.py` if needed)
- A short note in `README.md` under "Compatibility"
- The setup steps for that agent

Don't change the existing `hooks/pre-prompt.sh` to "support both" — keep adapters separate so each one can be tuned to the agent's actual hook format.

## 3. Ranking strategies

The current ranker is keyword + regex with severity × recency × match-strength weighting. It's a deliberate choice — fast, predictable, no embeddings infra. But there are valid alternatives:

- Embedding-based semantic similarity (V3 plan)
- TF-IDF over the corpus
- Bayesian recency weighting

If you want to propose one, please:

1. Open an issue first describing the approach and expected tradeoff (precision/recall/latency/dependencies)
2. Implement as an alternative ranker the user can opt into via a config flag, **not** a replacement for the default
3. Include a benchmark on a small sample corpus showing the delta

## Bug reports

If the hook breaks your Claude Code session: that's a P0 (the fail-open guarantee is being violated). Open an issue with:

- The exact prompt that triggered it
- The contents of `~/.claude/experience/logs/injections.jsonl` for the affected session
- macOS / Linux version, Python version
- The output of `bash -x ~/.claude/skills/experience-layer/hooks/pre-prompt.sh < /tmp/your-prompt.json`

## Style

- Bash: POSIX-ish, fail-open, swallow errors at the boundary
- Python: 3.9+, no third-party deps beyond PyYAML, type hints where they help readability
- Markdown: keep lines under ~100 chars, use sentence-case for headings

No formal linter required. Read the existing code before submitting.

## License

By contributing, you agree your contributions are licensed under the MIT License (same as the rest of the project).
