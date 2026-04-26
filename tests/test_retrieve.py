"""Unit and integration tests for lib/retrieve.py.

Run from repo root:
    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

import retrieve  # noqa: E402


# ---------- fixtures ----------

VALID_PATTERN = """---
id: pa-test-rate-limit
name: Test pattern for rate limit
severity: high
domain: power-automate
triggers:
  keywords:
    - "flow trigger"
    - "every minute"
  regex:
    - "Power Automate.*every.*minute"
fix: |
  Concrete actionable advice with thresholds.
last_seen: 2026-04-18
provenance:
  url: "https://example.com/docs"
  session_id: null
  commit: null
review_status: validated
hits: 4
last_save_at: 2026-04-12
false_positives: 0
---

# Body
"""

PATTERN_NO_PROVENANCE = """---
id: bad-no-provenance
name: Should be rejected
severity: high
domain: power-automate
triggers:
  keywords: ["foo"]
fix: "irrelevant"
last_seen: 2026-04-18
provenance:
  url: null
  session_id: null
  commit: null
---

# Body
"""

PATTERN_ARCHIVED = """---
id: archived-pattern
name: Archived pattern
severity: high
domain: power-automate
triggers:
  keywords: ["archived"]
fix: "irrelevant"
last_seen: 2026-04-18
provenance:
  url: "https://example.com"
review_status: archived
---

# Body
"""

PATTERN_MALFORMED = """---
id: broken
not valid yaml: [
unclosed
---

# Body
"""

PATTERN_NO_FRONTMATTER = "# Just markdown\nNo frontmatter here.\n"


class CorpusFixture:
    """Builds a temporary HOME with a fresh experience-layer corpus."""

    def __init__(self):
        self.tmpdir = tempfile.mkdtemp(prefix="exp-layer-test-")
        self.home = Path(self.tmpdir) / "home"
        self.experience = self.home / ".claude" / "experience"
        for d in ("power-automate", "frontend", "general"):
            (self.experience / "global" / d).mkdir(parents=True, exist_ok=True)
        (self.experience / "logs").mkdir(parents=True, exist_ok=True)

    def write(self, domain: str, filename: str, content: str) -> Path:
        path = self.experience / "global" / domain / filename
        path.write_text(content)
        return path

    def cleanup(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------- _load_pattern ----------


class TestLoadPattern(unittest.TestCase):
    def setUp(self):
        self.fix = CorpusFixture()

    def tearDown(self):
        self.fix.cleanup()

    def test_valid_pattern_loads(self):
        path = self.fix.write("power-automate", "valid.md", VALID_PATTERN)
        pat = retrieve._load_pattern(path)
        self.assertIsNotNone(pat)
        self.assertEqual(pat["id"], "pa-test-rate-limit")
        self.assertEqual(pat["severity"], "high")

    def test_missing_provenance_rejected(self):
        path = self.fix.write("power-automate", "noprov.md", PATTERN_NO_PROVENANCE)
        self.assertIsNone(retrieve._load_pattern(path))

    def test_archived_pattern_rejected(self):
        path = self.fix.write("power-automate", "arch.md", PATTERN_ARCHIVED)
        self.assertIsNone(retrieve._load_pattern(path))

    def test_malformed_yaml_rejected(self):
        path = self.fix.write("power-automate", "bad.md", PATTERN_MALFORMED)
        self.assertIsNone(retrieve._load_pattern(path))

    def test_no_frontmatter_rejected(self):
        path = self.fix.write("power-automate", "plain.md", PATTERN_NO_FRONTMATTER)
        self.assertIsNone(retrieve._load_pattern(path))

    def test_nonexistent_file_returns_none(self):
        self.assertIsNone(retrieve._load_pattern(Path("/nonexistent/path/x.md")))


class TestLoadPatternDiagnostic(unittest.TestCase):
    """The diagnostic variant returns explicit rejection reasons (used by lib/diag.py)."""

    def setUp(self):
        self.fix = CorpusFixture()

    def tearDown(self):
        self.fix.cleanup()

    def test_valid_returns_no_reason(self):
        path = self.fix.write("power-automate", "v.md", VALID_PATTERN)
        pat, reason = retrieve._load_pattern_diagnostic(path)
        self.assertIsNotNone(pat)
        self.assertIsNone(reason)

    def test_missing_provenance_reason(self):
        path = self.fix.write("power-automate", "p.md", PATTERN_NO_PROVENANCE)
        pat, reason = retrieve._load_pattern_diagnostic(path)
        self.assertIsNone(pat)
        self.assertEqual(reason, "missing_provenance")

    def test_archived_reason(self):
        path = self.fix.write("power-automate", "a.md", PATTERN_ARCHIVED)
        pat, reason = retrieve._load_pattern_diagnostic(path)
        self.assertIsNone(pat)
        self.assertEqual(reason, "archived")

    def test_malformed_yaml_reason(self):
        path = self.fix.write("power-automate", "m.md", PATTERN_MALFORMED)
        pat, reason = retrieve._load_pattern_diagnostic(path)
        self.assertIsNone(pat)
        self.assertEqual(reason, "malformed_yaml")

    def test_no_frontmatter_reason(self):
        path = self.fix.write("power-automate", "n.md", PATTERN_NO_FRONTMATTER)
        pat, reason = retrieve._load_pattern_diagnostic(path)
        self.assertIsNone(pat)
        self.assertEqual(reason, "no_frontmatter")

    def test_read_error_reason(self):
        pat, reason = retrieve._load_pattern_diagnostic(Path("/nonexistent/x.md"))
        self.assertIsNone(pat)
        self.assertEqual(reason, "read_error")


# ---------- _kill_switch ----------


class TestKillSwitch(unittest.TestCase):
    def setUp(self):
        self.fix = CorpusFixture()
        os.environ.pop("EXPERIENCE_LAYER", None)

    def tearDown(self):
        self.fix.cleanup()
        os.environ.pop("EXPERIENCE_LAYER", None)

    def test_no_kill_switch(self):
        self.assertFalse(retrieve._kill_switch(Path(self.fix.tmpdir)))

    def test_env_var_off(self):
        os.environ["EXPERIENCE_LAYER"] = "off"
        self.assertTrue(retrieve._kill_switch(Path(self.fix.tmpdir)))

    def test_env_var_off_case_insensitive(self):
        os.environ["EXPERIENCE_LAYER"] = "OFF"
        self.assertTrue(retrieve._kill_switch(Path(self.fix.tmpdir)))

    def test_env_var_on_does_not_disable(self):
        os.environ["EXPERIENCE_LAYER"] = "on"
        self.assertFalse(retrieve._kill_switch(Path(self.fix.tmpdir)))

    def test_disable_file_present(self):
        (Path(self.fix.tmpdir) / ".experience-disabled").touch()
        self.assertTrue(retrieve._kill_switch(Path(self.fix.tmpdir)))


# ---------- _score ----------


class TestScore(unittest.TestCase):
    def _pattern(self, **overrides):
        base = {
            "severity": "med",
            "triggers": {"keywords": [], "regex": []},
            "last_seen": None,
            "false_positives": 0,
            "hits": 0,
        }
        base.update(overrides)
        return base

    def test_no_match_returns_zero(self):
        pat = self._pattern(triggers={"keywords": ["xyz"]})
        score, fired = retrieve._score(pat, "completely unrelated prompt")
        self.assertEqual(score, 0.0)
        self.assertEqual(fired, [])

    def test_keyword_match_fires(self):
        pat = self._pattern(severity="med", triggers={"keywords": ["foobar"]})
        score, fired = retrieve._score(pat, "I'm dealing with foobar today")
        self.assertGreater(score, 0)
        self.assertIn("foobar", fired)

    def test_regex_weight_higher_than_keyword(self):
        prompt = "this matches a thing"
        kw = self._pattern(triggers={"keywords": ["matches a thing"]})
        rx = self._pattern(triggers={"regex": ["matches a thing"]})
        kw_score, _ = retrieve._score(kw, prompt)
        rx_score, _ = retrieve._score(rx, prompt)
        self.assertGreater(rx_score, kw_score)

    def test_severity_high_beats_low(self):
        triggers = {"keywords": ["foo"]}
        low = self._pattern(severity="low", triggers=triggers)
        high = self._pattern(severity="high", triggers=triggers)
        low_s, _ = retrieve._score(low, "foo")
        high_s, _ = retrieve._score(high, "foo")
        self.assertGreater(high_s, low_s)

    def test_fp_penalty_applied_when_fps_exceed_hits(self):
        triggers = {"keywords": ["foo"]}
        clean = self._pattern(triggers=triggers, false_positives=0, hits=5)
        noisy = self._pattern(triggers=triggers, false_positives=5, hits=0)
        clean_s, _ = retrieve._score(clean, "foo")
        noisy_s, _ = retrieve._score(noisy, "foo")
        self.assertGreater(clean_s, noisy_s)

    def test_invalid_regex_ignored_gracefully(self):
        pat = self._pattern(triggers={"regex": ["[unclosed"]})
        score, fired = retrieve._score(pat, "anything")
        self.assertEqual(score, 0)
        self.assertEqual(fired, [])

    def test_recency_boost_for_fresh_pattern(self):
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=5)).date().isoformat()
        old = (datetime.now() - timedelta(days=300)).date().isoformat()
        triggers = {"keywords": ["foo"]}
        fresh = self._pattern(triggers=triggers, last_seen=recent)
        stale = self._pattern(triggers=triggers, last_seen=old)
        fresh_s, _ = retrieve._score(fresh, "foo")
        stale_s, _ = retrieve._score(stale, "foo")
        self.assertGreater(fresh_s, stale_s)


# ---------- _detect_domains ----------


class TestDetectDomains(unittest.TestCase):
    def test_power_automate_keyword_detected(self):
        domains = retrieve._detect_domains(
            "Power Automate flow", ["power-automate", "frontend", "general"]
        )
        self.assertIn("power-automate", domains)

    def test_solana_keyword_detected(self):
        domains = retrieve._detect_domains(
            "Solana anchor program", ["power-automate", "solana", "general"]
        )
        self.assertIn("solana", domains)

    def test_general_always_included_when_available(self):
        domains = retrieve._detect_domains("foo", ["frontend", "general"])
        self.assertIn("general", domains)


# ---------- integration via subprocess ----------


class TestRetrieveIntegration(unittest.TestCase):
    def setUp(self):
        self.fix = CorpusFixture()
        self.fix.write("power-automate", "rate.md", VALID_PATTERN)

    def tearDown(self):
        self.fix.cleanup()

    def _run(self, prompt: str, env_extra: dict | None = None):
        env = os.environ.copy()
        env["EXPERIENCE_LAYER_HOME"] = str(self.fix.home / ".claude")
        env.pop("EXPERIENCE_LAYER", None)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(ROOT / "lib" / "retrieve.py")],
            input=json.dumps({"prompt": prompt}),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.fix.tmpdir),
        )

    def test_matching_prompt_emits_warning(self):
        result = self._run("Create a Power Automate flow that runs every minute")
        self.assertEqual(result.returncode, 0)
        self.assertIn("experience-layer warnings", result.stdout)
        self.assertIn("pa-test-rate-limit", result.stdout)

    def test_unrelated_prompt_silent(self):
        result = self._run("write a haiku about clouds")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_kill_switch_silences(self):
        result = self._run(
            "Power Automate flow trigger every minute",
            env_extra={"EXPERIENCE_LAYER": "off"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_empty_stdin_silent(self):
        env = os.environ.copy()
        env["EXPERIENCE_LAYER_HOME"] = str(self.fix.home / ".claude")
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "retrieve.py")],
            input="",
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_malformed_json_silent(self):
        env = os.environ.copy()
        env["EXPERIENCE_LAYER_HOME"] = str(self.fix.home / ".claude")
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "retrieve.py")],
            input="not json {{{",
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_injection_logged(self):
        self._run("Create a Power Automate flow that runs every minute")
        log = self.fix.experience / "logs" / "injections.jsonl"
        self.assertTrue(log.exists())
        last = log.read_text().strip().splitlines()[-1]
        entry = json.loads(last)
        self.assertIn("pa-test-rate-limit", entry["patterns_injected"])
        self.assertIn("ts", entry)
        self.assertIn("prompt_hash", entry)


if __name__ == "__main__":
    unittest.main()
