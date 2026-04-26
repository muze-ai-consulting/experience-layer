#!/usr/bin/env python3
"""
experience-layer benchmark.

Two evaluations:

  1. Precision / recall / F1 on a hand-labeled set of 20 prompts.
     Corpus = the patterns in `examples/`, organized by their `domain`
     frontmatter field. should_trigger=true cases name an expected
     pattern; should_trigger=false cases probe for false positives.

  2. Timing distribution (mean, p50, p95, p99) over N iterations of the
     full hook pipeline (subprocess spawn included — this is the latency
     the user actually sees per prompt).

Usage:
    python3 benchmark/run.py
    python3 benchmark/run.py --iterations 200      # heavier timing run
    python3 benchmark/run.py --no-timing           # precision/recall only
    python3 benchmark/run.py --output results.md   # custom output path

Outputs:
    benchmark/results.md     human-readable
    benchmark/results.json   machine-readable (suitable for tracking over time)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETRIEVE = ROOT / "lib" / "retrieve.py"
EXAMPLES_DIR = ROOT / "examples"
EVAL_FILE = ROOT / "benchmark" / "eval.json"


# ---------- corpus setup ----------

DOMAIN_RE = re.compile(r"^domain:\s*(\S+)\s*$", re.MULTILINE)


def setup_corpus(home: Path) -> dict[str, int]:
    """Copy examples/*.md into a fresh corpus, organized by their `domain` frontmatter."""
    target = home / "experience" / "global"
    target.mkdir(parents=True, exist_ok=True)
    (home / "experience" / "logs").mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for pattern_file in sorted(EXAMPLES_DIR.glob("*.md")):
        text = pattern_file.read_text()
        m = DOMAIN_RE.search(text)
        if not m:
            continue
        domain = m.group(1).strip().strip('"').strip("'")
        dest_dir = target / domain
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pattern_file, dest_dir / pattern_file.name)
        counts[domain] = counts.get(domain, 0) + 1
    return counts


# ---------- runner ----------


def run_retrieve(prompt: str, home: Path) -> tuple[str, float]:
    """Run retrieve.py against the corpus rooted at `home`. Return (stdout, elapsed_seconds)."""
    env = os.environ.copy()
    env["EXPERIENCE_LAYER_HOME"] = str(home)
    env.pop("EXPERIENCE_LAYER", None)
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(RETRIEVE)],
        input=json.dumps({"prompt": prompt}),
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed = time.perf_counter() - start
    return result.stdout, elapsed


# ---------- evaluation ----------


@dataclass
class CaseResult:
    prompt: str
    should_trigger: bool
    expected_pattern_id: str | None
    fired: bool
    matched_expected: bool
    classification: str  # TP / FP / FN / TN
    note: str | None = None


def precision_recall(home: Path) -> tuple[dict, list[CaseResult]]:
    eval_data = json.loads(EVAL_FILE.read_text())
    cases = eval_data["cases"]
    results: list[CaseResult] = []

    tp = fp = fn = tn = 0
    for case in cases:
        prompt = case["prompt"]
        should = bool(case["should_trigger"])
        expected = case.get("expected_pattern_id")
        note = case.get("_note")

        stdout, _ = run_retrieve(prompt, home)
        fired = "experience-layer warnings" in stdout
        matched_expected = bool(expected and expected in stdout)

        if should:
            if fired and (not expected or matched_expected):
                klass = "TP"
                tp += 1
            else:
                klass = "FN"
                fn += 1
        else:
            if fired:
                klass = "FP"
                fp += 1
            else:
                klass = "TN"
                tn += 1

        results.append(
            CaseResult(
                prompt=prompt,
                should_trigger=should,
                expected_pattern_id=expected,
                fired=fired,
                matched_expected=matched_expected,
                classification=klass,
                note=note,
            )
        )

    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    summary = {
        "total": total,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }
    return summary, results


def timing(home: Path, iterations: int) -> dict:
    sample = "Create a Power Automate flow that runs every minute"
    # Warm-up to amortize Python import startup
    for _ in range(3):
        run_retrieve(sample, home)

    times_ms: list[float] = []
    for _ in range(iterations):
        _, elapsed = run_retrieve(sample, home)
        times_ms.append(elapsed * 1000)

    times_ms.sort()
    return {
        "iterations": iterations,
        "mean_ms": round(statistics.mean(times_ms), 1),
        "stdev_ms": round(statistics.stdev(times_ms), 1) if len(times_ms) > 1 else 0.0,
        "min_ms": round(times_ms[0], 1),
        "p50_ms": round(times_ms[len(times_ms) // 2], 1),
        "p95_ms": round(times_ms[int(len(times_ms) * 0.95)], 1),
        "p99_ms": round(times_ms[int(len(times_ms) * 0.99)], 1),
        "max_ms": round(times_ms[-1], 1),
    }


# ---------- output ----------


def render_markdown(corpus: dict[str, int], pr_summary: dict, results: list[CaseResult],
                    timing_data: dict | None) -> str:
    lines: list[str] = []
    lines.append("# experience-layer benchmark")
    lines.append("")
    lines.append(f"_Run at {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append("## Corpus")
    lines.append("")
    total_patterns = sum(corpus.values())
    lines.append(f"{total_patterns} patterns loaded from `examples/`:")
    for d, n in sorted(corpus.items()):
        lines.append(f"- `{d}`: {n}")
    lines.append("")
    lines.append("## Precision / Recall")
    lines.append("")
    s = pr_summary
    lines.append(f"| metric | value |")
    lines.append(f"|---|---|")
    lines.append(f"| total cases | {s['total']} |")
    lines.append(f"| true positives  (fired correctly) | **{s['tp']}** |")
    lines.append(f"| true negatives  (silent correctly) | **{s['tn']}** |")
    lines.append(f"| false positives (fired wrongly)   | **{s['fp']}** |")
    lines.append(f"| false negatives (missed)          | **{s['fn']}** |")
    lines.append(f"| precision | **{s['precision']:.2f}** |")
    lines.append(f"| recall    | **{s['recall']:.2f}** |")
    lines.append(f"| F1        | **{s['f1']:.2f}** |")
    lines.append("")

    misses = [r for r in results if r.classification in ("FP", "FN")]
    if misses:
        lines.append("### Misses")
        lines.append("")
        for r in misses:
            lines.append(f"- **[{r.classification}]** `{r.prompt[:80]}{'…' if len(r.prompt) > 80 else ''}`")
            if r.note:
                lines.append(f"  - {r.note}")
        lines.append("")
    else:
        lines.append("_No misses — every case classified correctly._")
        lines.append("")

    if timing_data:
        t = timing_data
        lines.append("## Timing")
        lines.append("")
        lines.append(f"_{t['iterations']} iterations of the full retrieve.py subprocess pipeline. "
                     "Includes Python interpreter startup — this is the latency a UserPromptSubmit "
                     "hook adds to each prompt._")
        lines.append("")
        lines.append(f"| stat | ms |")
        lines.append(f"|---|---|")
        lines.append(f"| mean | {t['mean_ms']:.1f} |")
        lines.append(f"| stdev | {t['stdev_ms']:.1f} |")
        lines.append(f"| min | {t['min_ms']:.1f} |")
        lines.append(f"| p50 | {t['p50_ms']:.1f} |")
        lines.append(f"| p95 | {t['p95_ms']:.1f} |")
        lines.append(f"| p99 | {t['p99_ms']:.1f} |")
        lines.append(f"| max | {t['max_ms']:.1f} |")
        lines.append("")

    return "\n".join(lines)


def render_console(corpus: dict[str, int], pr_summary: dict, results: list[CaseResult],
                   timing_data: dict | None) -> str:
    lines: list[str] = []
    lines.append("experience-layer benchmark")
    lines.append("=" * 30)
    lines.append("")
    total_patterns = sum(corpus.values())
    lines.append(f"Corpus: {total_patterns} patterns ({', '.join(f'{d}={n}' for d, n in sorted(corpus.items()))})")
    lines.append("")
    s = pr_summary
    lines.append(f"Precision/Recall ({s['total']} cases)")
    lines.append(f"  TP={s['tp']}  FP={s['fp']}  FN={s['fn']}  TN={s['tn']}")
    lines.append(f"  precision={s['precision']:.2f}  recall={s['recall']:.2f}  F1={s['f1']:.2f}")
    misses = [r for r in results if r.classification in ("FP", "FN")]
    if misses:
        lines.append("")
        lines.append("  Misses:")
        for r in misses:
            head = r.prompt[:70] + ("…" if len(r.prompt) > 70 else "")
            lines.append(f"    [{r.classification}] {head}")
    if timing_data:
        t = timing_data
        lines.append("")
        lines.append(f"Timing ({t['iterations']} iter, ms — includes Python startup)")
        lines.append(f"  mean={t['mean_ms']:.1f}  p50={t['p50_ms']:.1f}  p95={t['p95_ms']:.1f}  p99={t['p99_ms']:.1f}")
    return "\n".join(lines)


# ---------- main ----------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=50,
                        help="Number of iterations for the timing run (default: 50)")
    parser.add_argument("--no-timing", action="store_true",
                        help="Skip the timing run")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark" / "results.md",
                        help="Markdown output path (default: benchmark/results.md)")
    parser.add_argument("--json-output", type=Path, default=ROOT / "benchmark" / "results.json",
                        help="JSON output path (default: benchmark/results.json)")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="exp-bench-") as tmpdir:
        home = Path(tmpdir)
        corpus = setup_corpus(home)
        pr_summary, results = precision_recall(home)
        timing_data = None if args.no_timing else timing(home, args.iterations)

    # Console
    print(render_console(corpus, pr_summary, results, timing_data))

    # Markdown
    md = render_markdown(corpus, pr_summary, results, timing_data)
    args.output.write_text(md)

    # JSON (machine-readable, tracked over time)
    json_payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "corpus": corpus,
        "summary": pr_summary,
        "cases": [asdict(r) for r in results],
        "timing": timing_data,
    }
    args.json_output.write_text(json.dumps(json_payload, indent=2))


if __name__ == "__main__":
    main()
