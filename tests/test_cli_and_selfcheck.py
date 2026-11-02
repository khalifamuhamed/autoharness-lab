import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from autoharness_lab import selfcheck
from autoharness_lab.cli import main
from autoharness_lab.paths import REPO_ROOT


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(list(argv))
        return code, buf.getvalue()

    def test_demo_sample_end_to_end_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "r.html"
            code, text = self.run_cli("demo", "--mode", "sample", "--out", str(out))
            self.assertEqual(code, 0)
            html = out.read_text(encoding="utf-8")
            self.assertIn("SAMPLE / EXAMPLE DATA", html)
            self.assertIn("92015c0", text)

    def test_helpers_via_cli(self):
        self.run_cli("sample")
        for cmd in ("where", "list"):
            code, text = self.run_cli(cmd, "--mode", "sample")
            self.assertEqual(code, 0, cmd)
        code, text = self.run_cli("show", "sample-testing-conventions", "--mode", "sample")
        self.assertEqual(code, 0)
        self.assertIn("السبب", text)

    def test_module_entry_point_runs(self):
        r = subprocess.run([sys.executable, "-m", "autoharness_lab", "--version"], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("autoharness-lab", r.stdout)

    def test_doctor_is_honest_without_login(self):
        code, text = self.run_cli("doctor")
        self.assertIn("92015c0b2583072d892b54ab83352ad3490c0a7f", text)


class SelfCheckTests(unittest.TestCase):
    def test_all_selfchecks_pass(self):
        failed = [(t, d) for t, ok, d in selfcheck.run_all() if not ok]
        self.assertEqual(failed, [])


if __name__ == "__main__":
    unittest.main()
