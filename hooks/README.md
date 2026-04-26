# Hooks (agent adapters)

Each file in this directory is a thin adapter between a specific agent's pre-prompt hook mechanism and the agent-agnostic core (`lib/retrieve.py`, `lib/nudge.py`).

| File | Agent |
|---|---|
| `claude-code.sh` | [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) `UserPromptSubmit` hook |

## The contract (what an adapter must do)

An adapter is a script the agent invokes before generation. It must:

1. **Read JSON from stdin** containing at least `prompt` (the user's prompt as a string). Other fields are tolerated and ignored.
2. **Pipe that JSON to `lib/retrieve.py`** via stdin. Capture stdout.
3. **Pipe that JSON to `lib/nudge.py`** via stdin. Capture stdout.
4. **Concatenate both outputs** (retrieve first, then nudge, separated by a blank line) and emit on its own stdout. The agent will inject this text as additional context.
5. **Honor kill switches before doing any work**:
   - `EXPERIENCE_LAYER=off` env var → exit 0 silently.
   - `<project-root>/.experience-disabled` file → exit 0 silently.
6. **Be fail-open**: any error inside the adapter must exit 0 with empty stdout. Use `set +e`, traps, and `2>/dev/null` to swallow noise. The hook must NEVER block generation.
7. **Apply hard timeouts where available** (`timeout` / `gtimeout`): 2s for retrieve, 1s for nudge. If neither command is present, run without an external timeout — the scripts have their own bounded behavior.
8. **Resolve `$LIB_DIR` relative to its own location**, so the skill works regardless of where it's installed.

The core libraries (`lib/retrieve.py`, `lib/nudge.py`) read JSON from stdin, write markdown to stdout, and write logs to `$EXPERIENCE_LAYER_HOME/experience/logs/` (default `~/.claude/`). Adapters don't need to know what's inside — they just have to deliver stdin/stdout.

## Adding an adapter for another agent

If your agent doesn't use a `UserPromptSubmit`-style hook, the work is to figure out:

- **How to receive the prompt before generation** (event name, signal, IPC mechanism)
- **What input format the agent provides** (your adapter is responsible for parsing whatever the agent sends and emitting the JSON shape `lib/retrieve.py` expects)
- **How to deliver the output back** (some agents take JSON, some take stdout, some need a callback)

Once you have those, the adapter is usually 30-50 lines of bash or Python. Use `claude-code.sh` as a template.

After writing the adapter:

1. Drop it in `hooks/<agent>.sh`
2. Update `install.sh` if it's worth registering automatically, OR add a section in `README.md` showing the manual registration step for that agent
3. Open a PR — see `CONTRIBUTING.md`

## What the core does NOT depend on

Things the adapter does NOT need to provide:
- Project root detection (`lib/retrieve.py` walks up from `cwd` looking for `.git`)
- Pattern loading or YAML parsing
- Scoring, ranking, or rendering
- Logging — `lib/retrieve.py` writes to `$EXPERIENCE_LAYER_HOME/experience/logs/` directly

The adapter is purely a transport layer. Keep it that way.
