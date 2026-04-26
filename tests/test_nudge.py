"""Unit and integration tests for lib/nudge.py."""
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

import nudge  # noqa: E402


class TestDetectRetry(unittest.TestCase):
    # --- English positives ---
    def test_english_not_working(self):
        self.assertTrue(nudge.detect_retry("that's not working at all"))

    def test_english_try_again(self):
        self.assertTrue(nudge.detect_retry("can you try again please"))

    def test_english_doesnt_work(self):
        self.assertTrue(nudge.detect_retry("that doesn't work"))

    def test_english_failed(self):
        self.assertTrue(nudge.detect_retry("the build failed"))

    def test_english_broken(self):
        self.assertTrue(nudge.detect_retry("the deploy is broken"))

    def test_english_still_failing(self):
        self.assertTrue(nudge.detect_retry("it's still failing"))

    # --- Spanish positives ---
    def test_spanish_no_funciono(self):
        self.assertTrue(nudge.detect_retry("eso no funciono"))

    def test_spanish_no_funciono_acentuado(self):
        self.assertTrue(nudge.detect_retry("eso no funcionó"))

    def test_spanish_intenta_de_nuevo(self):
        self.assertTrue(nudge.detect_retry("intenta de nuevo por favor"))

    def test_spanish_intentemoslo_otra_vez(self):
        self.assertTrue(nudge.detect_retry("intentémoslo otra vez"))

    def test_spanish_no_anduvo(self):
        self.assertTrue(nudge.detect_retry("eso no anduvo"))

    def test_spanish_volve_a_probar(self):
        self.assertTrue(nudge.detect_retry("volvé a probar el script"))

    def test_spanish_sigue_roto(self):
        self.assertTrue(nudge.detect_retry("sigue roto el deploy"))

    # --- Negatives ---
    def test_normal_prompt_silent(self):
        self.assertFalse(nudge.detect_retry("write a function that sorts a list"))

    def test_empty_prompt_silent(self):
        self.assertFalse(nudge.detect_retry(""))

    def test_word_again_alone_does_not_fire(self):
        # "try again" fires; bare "again" should NOT
        self.assertFalse(nudge.detect_retry("show me the times again later"))

    def test_unrelated_failure_word(self):
        # "fail" without inflection / context shouldn't match "failed" pattern
        self.assertFalse(nudge.detect_retry("on the verge of fail-fast principle"))


class TestNudgeCLI(unittest.TestCase):
    def _run(self, payload: str):
        return subprocess.run(
            [sys.executable, str(ROOT / "lib" / "nudge.py")],
            input=payload,
            capture_output=True,
            text=True,
        )

    def test_retry_signal_produces_output(self):
        result = self._run(json.dumps({"prompt": "that's not working"}))
        self.assertEqual(result.returncode, 0)
        self.assertIn("nudge", result.stdout.lower())

    def test_normal_silent(self):
        result = self._run(json.dumps({"prompt": "hello world"}))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_malformed_json_silent(self):
        result = self._run("not json")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_empty_stdin_silent(self):
        result = self._run("")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


class TestNudgeLogging(unittest.TestCase):
    """When the nudge fires it should write to logs/nudges.jsonl. When silent, no log."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="nudge-test-")
        self.exp_home = Path(self.tmpdir) / ".claude"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, prompt_payload: str):
        env = os.environ.copy()
        env["EXPERIENCE_LAYER_HOME"] = str(self.exp_home)
        return subprocess.run(
            [sys.executable, str(ROOT / "lib" / "nudge.py")],
            input=prompt_payload,
            capture_output=True,
            text=True,
            env=env,
        )

    def _log_path(self):
        return self.exp_home / "experience" / "logs" / "nudges.jsonl"

    def test_fire_writes_log(self):
        self._run(json.dumps({"prompt": "that's not working"}))
        self.assertTrue(self._log_path().exists())
        line = self._log_path().read_text().strip().splitlines()[-1]
        entry = json.loads(line)
        self.assertIn("ts", entry)
        self.assertIn("prompt_hash", entry)
        self.assertIn("context_size_in", entry)

    def test_no_fire_no_log(self):
        self._run(json.dumps({"prompt": "hello world"}))
        # Either the log file doesn't exist, or it has no entries.
        if self._log_path().exists():
            self.assertEqual(self._log_path().read_text().strip(), "")

    def test_log_entry_does_not_contain_prompt_text(self):
        # Privacy: log stores hash, not raw prompt.
        secret = "secret token abc123 should never appear"
        self._run(json.dumps({"prompt": f"that didn't work {secret}"}))
        contents = self._log_path().read_text()
        self.assertNotIn(secret, contents)
        self.assertNotIn("that didn't work", contents)


if __name__ == "__main__":
    unittest.main()
