---
name: experience-layer
description: Manages the experience-layer corpus — a cross-project library of past failures, anti-patterns, and lessons-learned that get auto-injected into Claude's context BEFORE generation via a UserPromptSubmit hook. Invoke this skill whenever the user wants to capture a new failure pattern, mark a recently-injected warning as saved or false-positive, onboard to a new domain, tune injection thresholds, debug match behavior, or check experience-layer status. Also invoke when the user mentions phrases like "experience layer", "exp-layer", "scar tissue", "anti-pattern", "lesson learned", "I've been burned by this", "I don't want to repeat this mistake", or related concepts — even when they don't explicitly say "experience-layer". The pre-flight injection itself runs automatically via the hook (configured in settings.json) — this skill is the management surface.
---

# Experience Layer

Always-on layer that simulates "scar-tissue" experience for Claude Code. Reads a markdown corpus of past failures, matches against the incoming prompt via regex/keyword triggers, and injects the top-3 relevant warnings BEFORE Claude generates.

## Why this exists

LLMs have broad knowledge but lack iterated experience — the "I've burned myself on this before" instinct. Static rules files (CLAUDE.md, .cursorrules) are read-once at session start and don't adapt. Generic memory layers (mem0, MemGPT) don't specialize on failures. This skill closes that gap with structured, scored, per-domain failure injection.

## Architecture (three independent pieces)

1. **Hook** — `hooks/claude-code.sh` runs on every `UserPromptSubmit`. Calls `lib/retrieve.py` and `lib/nudge.py` with hard timeouts (where `timeout`/`gtimeout` is available). Fail-open: any error → silent skip, never blocks generation. Other agents need their own adapter — see `hooks/README.md`.

2. **Corpus** — markdown files with structured frontmatter:
   - Global: `~/.claude/experience/global/<domain>/*.md`
   - Project: `<git-root>/.claude/experience/*.md`
   - Logs: `~/.claude/experience/logs/{injections,saves,false_positives}.jsonl`

3. **Slash commands** (this skill is their home):
   | Command | Purpose |
   |---|---|
   | `/exp-capture` | Auto-drafts a pattern from the last N turns, user approves/edits |
   | `/exp-saved <id>` | Mark an injected warning as having prevented a bug |
   | `/exp-falsepositive <id>` | Reduce a pattern's score (didn't apply) |
   | `/exp-onboard` | 15-min wizard: 5 starter patterns from one domain |
   | `/exp-tune` | Review injection logs, propose threshold adjustments |
   | `/exp-status` | Corpus stats, recent injections, kill switch state |

## Kill switches (always available)

The hook honors three independent off switches, so a noisy or buggy corpus can be silenced without uninstalling:

- **Per project**: `touch <project-root>/.experience-disabled`
- **Global**: `export EXPERIENCE_LAYER=off`
- **Per session** (set in current shell): `export EXPERIENCE_LAYER=off`

The hook checks these first, before any corpus loading, to keep the no-op path under 50ms.

## Pattern format (full spec in `references/PATTERN_SPEC.md`)

Each pattern is a `.md` file with required YAML frontmatter:

```yaml
---
id: <domain>-YYYY-MM-DD-<slug>
name: <human-readable, ~10 words>
severity: low | med | high
domain: power-automate | solana | frontend | general | ...
triggers:
  keywords: ["...", "..."]
  regex: ["..."]
fix: |
  <multiline structured guidance>
last_seen: 2026-04-18
provenance:
  url: "..."           # at least one of url/session_id REQUIRED
  session_id: "..."
  commit: null
review_status: pending | validated | archived
hits: 0                 # incremented by /exp-saved
last_save_at: null
false_positives: 0      # incremented by /exp-falsepositive
---

# <title>

## Contexto
## Por qué warnings genéricos no lo capturan
## Qué hacer en su lugar
## Patrones relacionados
```

**Provenance is enforced at load**: a pattern with neither `url` nor `session_id` is rejected (anti-fabrication, per the *Context Injection Attacks* paper, arXiv:2405.20234).

## Retrieval algorithm (full spec in `references/RETRIEVAL.md`)

Per prompt:

1. Hook receives JSON via stdin: `{prompt, session_id, transcript_path, cwd, ...}`
2. Resolve project root: git → cwd
3. Detect candidate domains via keyword match in prompt
4. Load patterns from `global/<domain>/` ∪ `project/.claude/experience/`
5. Reject patterns with: missing provenance, `review_status: archived`, malformed YAML
6. Score each candidate: `severity_weight × recency_factor × match_strength`
7. Rank, take top-3
8. Render warnings (format in `references/INJECTION_FORMAT.md`) and emit to stdout
9. Append `{ts, prompt_hash, patterns_injected, context_size_in}` to `injections.jsonl`

Soft target: <500ms total. Hard timeout in hook: 2s for retrieve, 1s for nudge.

## When this skill is invoked directly

Map user intent to commands:

- *"capture this", "log this lesson", "add this as a pattern"* → run `commands/exp-capture.md`
- *"onboard me to <domain>", "seed power automate patterns"* → run `commands/exp-onboard.md`
- *"experience status", "how is exp-layer doing"* → run `commands/exp-status.md`
- *"tune", "reduce noise", "review what's firing"* → run `commands/exp-tune.md`
- *"that warning saved me", "mark X as saved"* → run `commands/exp-saved.md`
- *"that warning was wrong", "false positive"* → run `commands/exp-falsepositive.md`

For each, read the corresponding `commands/<name>.md` and follow its instructions.

## Installation

One-time setup:

```bash
bash ~/.claude/skills/experience-layer/install.sh
```

`install.sh` is idempotent and does:

1. Creates `~/.claude/experience/{global/{power-automate,solana,frontend,general},logs}/`
2. Copies `commands/exp-*.md` into `~/.claude/commands/`
3. Backs up `~/.claude/settings.json`, then registers the hook (no duplicate entries)
4. Installs PyYAML via `pip --user` if missing
5. Reminds user to run `/exp-onboard`

## Reference files

| File | When to read |
|---|---|
| `references/PATTERN_SPEC.md` | Creating, editing, or validating a pattern |
| `references/RETRIEVAL.md` | Debugging matches, tuning thresholds, understanding ranking |
| `references/INJECTION_FORMAT.md` | Modifying how warnings render |
| `commands/<name>.md` | Executing the specific slash command |

## Versioning

V1 (this version) covers: dual corpus, retrieval+injection, manual capture with LLM auto-draft, kill switches, logs, nudge for retry signals.

V2 (planned): web search pre-flight with triggers + cache, automated recency decay, `/exp-tune` auto-application of suggestions.

V3 (planned): automatic capture from transcript, embedding-based semantic match, cross-project pattern mining.
