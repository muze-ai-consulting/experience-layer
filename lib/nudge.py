#!/usr/bin/env python3
"""
experience-layer passive nudge.
Detects retry / "this didn't work" signals in the user prompt and emits
a one-line hint suggesting /exp-capture so the failure can be captured.
Fail-open: any error → silent exit 0.
"""
from __future__ import annotations

import json
import re
import sys

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


def main() -> None:
    prompt = _read_prompt()
    if detect_retry(prompt):
        sys.stdout.write(
            "💡 _experience-layer nudge: detected a retry/failure signal in your prompt. "
            "If the previous turn failed in a way you don't want to repeat, run "
            "`/exp-capture` to save the lesson._\n"
        )


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        sys.exit(0)
