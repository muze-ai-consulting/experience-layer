# Retrieval — match algorithm and ranking

Defined in `lib/retrieve.py`. This document explains the algorithm so it's tunable without re-reading the code.

## Pipeline

```
stdin (JSON: {prompt, ...})
   ↓
[1] Read prompt + check kill switches
   ↓
[2] Resolve project root (git → cwd)
   ↓
[3] Detect candidate domains via keyword match
   ↓
[4] Load patterns from global/<domain>/ + project/.claude/experience/
   ↓
[5] Reject malformed YAML, missing provenance, archived
   ↓
[6] Score each pattern: severity × recency × match_strength × fp_penalty
   ↓
[7] Filter: score ≥ MIN_SCORE
   ↓
[8] Sort desc, take top-N
   ↓
[9] Render warnings
   ↓
[10] Append injection to logs/injections.jsonl
   ↓
stdout (markdown warnings)
```

## Tunables (defined as constants at top of `retrieve.py`)

```python
SEVERITY_WEIGHT = {"high": 3.0, "med": 2.0, "low": 1.0}
RECENCY_FRESH_DAYS = 30        # +20% boost if last_seen within this window
RECENCY_DECAY_DAYS = 180       # -50% if last_seen older than this
TOP_N = 3                      # max warnings injected per prompt
MIN_SCORE = 0.5                # below this, drop the candidate
KEYWORD_HIT_WEIGHT = 1.0       # each keyword match adds this
REGEX_HIT_WEIGHT = 2.0         # each regex match adds this (regex is more specific)
```

To tune: edit those constants. The hook re-runs Python on every prompt, so changes take effect immediately.

## Scoring formula

```
match_strength = sum(KEYWORD_HIT_WEIGHT for kw in keywords if kw.lower() in prompt.lower())
              + sum(REGEX_HIT_WEIGHT  for rx in regexes if re.search(rx, prompt, IGNORECASE))

if match_strength == 0:
    score = 0   # not a candidate

severity_w = SEVERITY_WEIGHT[severity]

recency_w = 1.0
if last_seen within RECENCY_FRESH_DAYS:    recency_w = 1.2
if last_seen older than RECENCY_DECAY_DAYS: recency_w = 0.5

fp_penalty = 1.0
if false_positives >= 3 and false_positives > hits: fp_penalty = 0.5

score = severity_w * recency_w * match_strength * fp_penalty
```

## Domain routing

To avoid loading every pattern on every prompt, the loader first detects which domain(s) the prompt seems to be about, then only opens those subdirectories. The mapping lives in `DOMAIN_KEYWORDS` inside `retrieve.py`:

```python
DOMAIN_KEYWORDS = {
    "power-automate": ["power automate", "flow trigger", "graph api", ...],
    "solana":         ["solana", "anchor", "@solana", "jito", ...],
    "frontend":       ["react", "tailwind", "vite", "next.js", ...],
    "general":        [],   # always considered
}
```

Project corpus (`<git-root>/.claude/experience/*.md`) is **always** loaded regardless of domain — project corpus is small enough that scanning all of it is cheap.

## Adding a new domain

1. Create `~/.claude/experience/global/<new-domain>/`
2. Add a row to `DOMAIN_KEYWORDS` in `retrieve.py` with a few seed keywords that uniquely identify prompts in that domain
3. Drop pattern files in the new directory
4. Test: `echo '{"prompt":"<test>"}' | python3 ~/.claude/skills/experience-layer/lib/retrieve.py`

## Performance budget

- Hard timeout in hook: **2s** for retrieve. Hook is fail-open so even if it hits the timeout, generation isn't blocked.
- Soft target: **<500ms** total.
- Optimizations available if corpus grows >200 patterns:
  - Index by domain (already done)
  - Precompile regex patterns (currently compiled on each call — fine for <100 patterns)
  - Cache parsed YAML (mtime-based) — V2 work

## Debugging matches

To see what would fire on a given prompt without actually triggering injection:

```bash
echo '{"prompt":"your test prompt here"}' | python3 ~/.claude/skills/experience-layer/lib/retrieve.py
```

If nothing fires:
- Check the prompt doesn't contain a kill switch trigger
- Check the corpus has loadable patterns: `ls ~/.claude/experience/global/*/`
- Verify provenance: open a pattern file and confirm `provenance.url` or `provenance.session_id` is set
- Lower `MIN_SCORE` temporarily to see weak matches

If something fires that shouldn't:
- Run `/exp-falsepositive <id>` to mark it
- Check `triggers.regex` for over-broad patterns
- Use `/exp-tune` after a week to see noisy patterns

## Logging

Every injection appends one JSONL line to `~/.claude/experience/logs/injections.jsonl`:

```json
{
  "ts": "2026-04-25T20:08:42.123456+00:00",
  "prompt_hash": "a1b2c3d4e5f6g7h8",
  "patterns_injected": ["pa-2026-02-03-flow-trigger-rate-limit", "..."],
  "context_size_in": 247
}
```

`prompt_hash` is sha256[:16] — enough to dedupe the same prompt repeated across days, never the prompt itself (privacy).
