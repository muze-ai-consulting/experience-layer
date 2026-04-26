#!/usr/bin/env python3
"""
Corpus diagnostics — walks all pattern files in the global + project corpus
and reports which loaded successfully vs which were rejected (with reason).

Used by /exp-status to give the user visibility into silently-rejected
patterns. The hot path (UserPromptSubmit hook) deliberately stays silent
on load failure so a malformed pattern can't break a Claude session;
this script is the "loud" companion that surfaces the silence on demand.

Usage:
    python3 lib/diag.py                # human-readable
    python3 lib/diag.py --json         # machine-readable JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# When run as a script, import siblings via direct path injection
sys.path.insert(0, str(Path(__file__).resolve().parent))

from retrieve import _experience_home, _load_pattern_diagnostic, _project_root  # noqa: E402


# Stable mapping of reason → human description, used in the output
REASON_DESCRIPTIONS = {
    "read_error": "File could not be read",
    "no_frontmatter": "Missing YAML frontmatter (file must start with ---)",
    "incomplete_frontmatter": "Frontmatter has no closing ---",
    "malformed_yaml": "YAML frontmatter failed to parse",
    "frontmatter_not_dict": "Top-level frontmatter is not a mapping",
    "provenance_not_dict": "provenance field is not an object",
    "missing_provenance": "Neither provenance.url nor provenance.session_id is set (anti-fabrication, see references/PATTERN_SPEC.md)",
    "archived": "review_status is archived (intentionally skipped)",
}


def inspect_corpus() -> dict:
    """Walk global + project corpora, classify each .md as loaded or rejected."""
    exp_home = _experience_home()
    global_dir = exp_home / "experience" / "global"
    project_root = _project_root()
    project_dir = project_root / ".claude" / "experience"

    loaded: list[dict] = []
    rejected: list[dict] = []

    for src_root, scope in [(global_dir, "global"), (project_dir, "project")]:
        if not src_root.exists() or not src_root.is_dir():
            continue
        for f in sorted(src_root.rglob("*.md")):
            if f.name.startswith("_"):
                continue  # skip _meta.json equivalents
            pat, reason = _load_pattern_diagnostic(f)
            try:
                rel_path = str(f.relative_to(src_root))
            except ValueError:
                rel_path = str(f)
            if pat:
                loaded.append({
                    "scope": scope,
                    "path": rel_path,
                    "id": pat.get("id"),
                    "domain": pat.get("domain"),
                    "severity": pat.get("severity"),
                    "review_status": pat.get("review_status") or "pending",
                    "hits": int(pat.get("hits") or 0),
                    "false_positives": int(pat.get("false_positives") or 0),
                })
            else:
                rejected.append({
                    "scope": scope,
                    "path": rel_path,
                    "reason": reason,
                    "description": REASON_DESCRIPTIONS.get(reason or "", "Unknown reason"),
                })

    # Aggregate by domain (loaded patterns only)
    by_domain: dict[str, int] = {}
    for p in loaded:
        d = p.get("domain") or "(unset)"
        by_domain[d] = by_domain.get(d, 0) + 1

    # Aggregate rejections by reason
    by_reason: dict[str, int] = {}
    for r in rejected:
        by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1

    return {
        "loaded": loaded,
        "rejected": rejected,
        "summary": {
            "loaded_count": len(loaded),
            "rejected_count": len(rejected),
            "loaded_by_domain": by_domain,
            "rejected_by_reason": by_reason,
        },
    }


def render_text(report: dict) -> str:
    s = report["summary"]
    lines: list[str] = []
    lines.append(f"Loaded:   {s['loaded_count']} pattern(s)")
    if s["loaded_by_domain"]:
        for d, n in sorted(s["loaded_by_domain"].items()):
            lines.append(f"  {d}: {n}")
    lines.append(f"Rejected: {s['rejected_count']} pattern(s)")
    if s["rejected_by_reason"]:
        for reason, n in sorted(s["rejected_by_reason"].items(), key=lambda x: -x[1]):
            lines.append(f"  {reason}: {n}")

    if report["rejected"]:
        lines.append("")
        lines.append("Rejected patterns (silent at load):")
        for r in report["rejected"]:
            lines.append(f"  [{r['reason']}] {r['scope']}/{r['path']}")
            lines.append(f"      → {r['description']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    report = inspect_corpus()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report))


if __name__ == "__main__":
    main()
