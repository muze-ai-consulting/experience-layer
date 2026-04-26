#!/usr/bin/env python3
"""
experience-layer passive nudge.
Detects retry / "this didn't work" signals in the user prompt and emits
a one-line hint suggesting /exp-capture so the failure can be captured.
Fail-open: any error → silent exit 0.

Logs each fire to ~/.claude/experience/logs/nudges.jsonl so /exp-tune can
report whether the nudge is producing signal or noise.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Spanish + English phrases that signal "the previous turn failed and the user is retrying".
RETRY_PATTERNS = [
    # Spanish
    r"\bno\s+funcion[oó]\b",
    r"\beso\s+fall[oó]\b",
    r"\bno\s+anduvo\b",
    r"\bno\s+pas[oó]\b",
    r"\bintenta(?:lo)?\s+de\s+nuevo\b",
    r"\bintent[ée](?:moslo)?\s+otra\s+vez\b",
    r"\bvolv[ée]\s+a\s+(?:probar|intentar|hacer)\b",
    r"\botra\s+vez\b",
    r"\bprob[áa]\s+otra\b",
    r"\bhac[ée]lo\s+de\s+nuevo\b",
    r"\b(?:est[áa]|sigue)\s+roto\b",
    r"\bsigue\s+(?:fallando|sin\s+andar)\b",
    # English
    r"\bnot\s+working\b",
    r"\btry\s+again\b",
    r"\bdoesn'?t\s+work\b",
    r"\bfailed\b",
    r"\bisn'?t\s+working\b",
    r"\bbroken\b",
    r"\bstill\s+(?:failing|broken|not\s+working)\b",
    r"\bthat'?s?\s+wrong\b",
    r"\bthat\s+didn'?t\s+work\b",
]

COMPILED = [re.compile(rx, re.IGNORECASE) for rx in RETRY_PATTERNS]


def _read_prompt() -> str:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw else {}
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("prompt") or data.get("user_prompt") or "")


def detect_retry(prompt: str) -> bool:
    if not prompt:
        return False
    return any(rx.search(prompt) for rx in COMPILED)


def _experience_home() -> Path:
    """Mirror retrieve.py's helper; duplicated to keep nudge.py free of yaml imports."""
    custom = os.environ.get("EXPERIENCE_LAYER_HOME")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".claude"


def _log_nudge(prompt: str) -> None:
    """Append one JSONL entry per fire so /exp-tune can score signal vs noise."""
    try:
        log_dir = _experience_home() / "experience" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "nudges.jsonl"
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8", "ignore")).hexdigest()[:16],
            "context_size_in": len(prompt),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # fail-open


def main() -> None:
    prompt = _read_prompt()
    if detect_retry(prompt):
        sys.stdout.write(
            "💡 _experience-layer nudge: detected a retry/failure signal in your prompt. "
            "If the previous turn failed in a way you don't want to repeat, run "
            "`/exp-capture` to save the lesson._\n"
        )
        _log_nudge(prompt)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        sys.exit(0)
