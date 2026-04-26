"""Unit and integration tests for lib/nudge.py."""
from __future__ import annotations

import json
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
