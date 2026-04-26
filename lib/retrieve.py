#!/usr/bin/env python3
"""
experience-layer corpus retriever
Reads stdin (Claude Code UserPromptSubmit JSON), loads patterns from
global + project corpus, ranks by severity x recency x match strength,
emits top-3 warnings to stdout. Logs the injection.

Fail-open by design: any uncaught exception → exit 0 with empty stdout.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # PyYAML
except ImportError:
    sys.exit(0)  # PyYAML missing → silent skip


# -------- Tunables (V1 defaults; /exp-tune can adjust later) --------
SEVERITY_WEIGHT = {"high": 3.0, "med": 2.0, "low": 1.0}
RECENCY_FRESH_DAYS = 30      # patterns seen in last 30d get a boost
RECENCY_DECAY_DAYS = 180     # patterns >180d lose half weight
TOP_N = 3
MIN_SCORE = 0.5              # drop weak matches
KEYWORD_HIT_WEIGHT = 1.0
REGEX_HIT_WEIGHT = 2.0       # regex hits are more specific → weighted higher

# Domain → seed keywords for routing the prompt to the right subdir.
# Patterns themselves still match by their own triggers — this is just to
# avoid loading EVERY pattern on every prompt.
DOMAIN_KEYWORDS = {
    "power-automate": [
        "power automate", "powerautomate", "flow trigger", "graph api",
        "sharepoint", "office 365", "dataverse", "ai builder",
    ],
    "solana": [
        "solana", "anchor", "@solana", "spl-token", "jito", "jupiter",
        "phantom", "metaplex", "mev", "lamports", "raydium",
    ],
    "frontend": [
        "react", "tailwind", "vite", "next.js", "shadcn", "tsx", "jsx",
        "component", "css", "vue", "svelte",
    ],
    "general": [],   # always considered
}


# -------- Helpers --------

def _read_stdin() -> str:
    try:
        raw = sys.stdin.read()
    except Exception:
        return ""
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    # Claude Code uses "prompt"; some other tools may use "user_prompt"
    return str(data.get("prompt") or data.get("user_prompt") or "")


def _experience_home() -> Path:
    """
    Root directory containing the experience/ subtree.
    Defaults to ~/.claude. Override with EXPERIENCE_LAYER_HOME for tests
    or multi-corpus setups. The env var should point at a directory that
    contains (or will contain) an experience/ subdirectory.
    """
    custom = os.environ.get("EXPERIENCE_LAYER_HOME")
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".claude"


def _project_root() -> Path:
    cwd = Path.cwd()
    p = cwd
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    return cwd


def _kill_switch(project_root: Path) -> bool:
    if os.environ.get("EXPERIENCE_LAYER", "").strip().lower() == "off":
        return True
    if (project_root / ".experience-disabled").exists():
        return True
    return False


def _detect_domains(prompt: str, available: list[str]) -> list[str]:
    p = prompt.lower()
    matched = []
    for d in available:
        if d == "general":
            continue
        kws = DOMAIN_KEYWORDS.get(d, [])
        if any(kw in p for kw in kws):
            matched.append(d)
    if "general" in available:
        matched.append("general")
    if not matched:
        matched = available  # fall back to scanning everything
    return matched


def _load_pattern(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    if not text.lstrip().startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None

    # Provenance check (anti-fabrication, per arXiv:2405.20234)
    prov = meta.get("provenance") or {}
    if not isinstance(prov, dict):
        return None
    if not (prov.get("url") or prov.get("session_id")):
        return None

    # Skip archived patterns
    if (meta.get("review_status") or "").lower() == "archived":
        return None

    meta["_path"] = str(path)
    meta["_body"] = parts[2].strip()
    return meta


def _score(pattern: dict, prompt: str) -> tuple[float, list[str]]:
    """Return (score, list of trigger strings that fired)."""
    p = prompt.lower()
    triggers = pattern.get("triggers") or {}
    if not isinstance(triggers, dict):
        return 0.0, []

    keywords = triggers.get("keywords") or []
    regexes = triggers.get("regex") or []
    fired: list[str] = []
    match_strength = 0.0

    if isinstance(keywords, list):
        for kw in keywords:
            if not isinstance(kw, str):
                continue
            if kw.lower() in p:
                match_strength += KEYWORD_HIT_WEIGHT
                fired.append(kw)

    if isinstance(regexes, list):
        for rx in regexes:
            if not isinstance(rx, str):
                continue
            try:
                if re.search(rx, prompt, re.IGNORECASE):
                    match_strength += REGEX_HIT_WEIGHT
                    fired.append(f"/{rx}/")
            except re.error:
                continue

    if match_strength == 0:
        return 0.0, []

    sev = (pattern.get("severity") or "low").lower()
    sev_w = SEVERITY_WEIGHT.get(sev, 1.0)

    # Recency
    recency_w = 1.0
    last_seen = pattern.get("last_seen")
    if last_seen:
        try:
            d = datetime.fromisoformat(str(last_seen).strip())
            days = (datetime.now() - d.replace(tzinfo=None)).days
            if days < RECENCY_FRESH_DAYS:
                recency_w = 1.2
            elif days > RECENCY_DECAY_DAYS:
                recency_w = 0.5
        except Exception:
            pass

    # False-positive penalty: if a pattern has many FPs and few hits, dampen it.
    fps = int(pattern.get("false_positives") or 0)
    hits = int(pattern.get("hits") or 0)
    fp_penalty = 1.0
    if fps >= 3 and fps > hits:
        fp_penalty = 0.5

    return sev_w * recency_w * match_strength * fp_penalty, fired


def _render(top: list[tuple[float, dict, list[str]]]) -> str:
    sev_icon = {"high": "🔴", "med": "🟡", "low": "⚪"}
    out = []
    out.append(f"⚠️ **experience-layer warnings** (top {len(top)} match{'es' if len(top) != 1 else ''})")
    out.append("")
    for _score, p, fired in top:
        sev = (p.get("severity") or "low").lower()
        icon = sev_icon.get(sev, "⚪")
        title = p.get("name") or "Untitled pattern"
        pid = p.get("id") or "no-id"
        fix = (p.get("fix") or "").strip()
        # Truncate long fixes for the inline warning; full text is in the file.
        if len(fix) > 400:
            fix = fix[:400].rstrip() + "…"
        prov = p.get("provenance") or {}
        src = prov.get("url") or prov.get("session_id") or "unknown"
        last_seen = p.get("last_seen") or "unknown"
        triggers_str = ", ".join(f"`{t}`" for t in fired[:4])
        out.append(f"{icon} **[{sev.upper()}]** {title}  `id={pid}`")
        out.append(f"   Trigger: {triggers_str}")
        out.append(f"   Rule: {fix}")
        out.append(f"   Source: {src}  (last seen {last_seen})")
        out.append("")
    out.append("_If a warning saved you: `/exp-saved <id>`. If it didn't apply: `/exp-falsepositive <id>`._")
    return "\n".join(out)


def _log_injection(prompt: str, injected_ids: list[str]) -> None:
    try:
        log_dir = _experience_home() / "experience" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "injections.jsonl"
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8", "ignore")).hexdigest()[:16],
            "patterns_injected": injected_ids,
            "context_size_in": len(prompt),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# -------- Main --------

def main() -> None:
    prompt = _read_stdin()
    if not prompt.strip():
        return

    project_root = _project_root()
    if _kill_switch(project_root):
        return

    exp_home = _experience_home()
    global_dir = exp_home / "experience" / "global"
    project_dir = project_root / ".claude" / "experience"

    # Discover available domains under global/
    available_domains: list[str] = []
    if global_dir.exists() and global_dir.is_dir():
        available_domains = sorted(
            d.name for d in global_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        )

    candidates: list[dict] = []

    # Global: domain-routed
    if available_domains:
        for d in _detect_domains(prompt, available_domains):
            domain_path = global_dir / d
            if domain_path.exists():
                for f in sorted(domain_path.glob("*.md")):
                    pat = _load_pattern(f)
                    if pat:
                        candidates.append(pat)

    # Project: load all (project corpus is small enough that we don't route)
    if project_dir.exists() and project_dir.is_dir():
        for f in sorted(project_dir.glob("*.md")):
            if f.name.startswith("_"):
                continue  # skip _meta.json equivalents
            pat = _load_pattern(f)
            if pat:
                candidates.append(pat)

    if not candidates:
        return

    scored: list[tuple[float, dict, list[str]]] = []
    for pat in candidates:
        score, fired = _score(pat, prompt)
        if score >= MIN_SCORE:
            scored.append((score, pat, fired))

    if not scored:
        return

    scored.sort(key=lambda x: -x[0])
    top = scored[:TOP_N]

    output = _render(top)
    sys.stdout.write(output + "\n")

    _log_injection(prompt, [p.get("id", "") for _, p, _ in top])


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        # Final fail-open guard.
        sys.exit(0)
