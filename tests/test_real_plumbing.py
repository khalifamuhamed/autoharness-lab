"""Plumbing tests for REAL mode using a stub `claude` (tests/fake_claude.py). They prove the harness builds
the right commands, installs/verifies the pin, waits for the drain, and renders a report. They do NOT prove
that real Claude/Autoharness learn anything; that needs a logged-in `claude` (see README)."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from autoharness_lab import real, report
from autoharness_lab.paths import load_pin
from autoharness_lab.store import Store

STUB = Path(__file__).with_name("fake_claude.py")


class RealPlumbing(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        STUB.chmod(STUB.stat().st_mode | stat.S_IXUSR)
        cfg = self.tmp / "cfg" / "plugins"
        cfg.mkdir(parents=True)
        pin = load_pin()
        (cfg / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {pin["plugin_id"]: [{"gitCommitSha": pin["commit"]}]}}))
        base = {real.CLAUDE_BIN_ENV: str(STUB), "CLAUDE_CONFIG_DIR": str(self.tmp / "cfg")}
        patcher = mock.patch.dict(os.environ, base)
        patcher.start()
        self.addCleanup(patcher.stop)
        for v in real.CRED_ENV_VARS:
            os.environ.pop(v, None)

    def test_preflight_ok_with_stub_login(self):
        pf = real.preflight()
        self.assertTrue(pf.ok, pf.reason)
        self.assertIn("stub", pf.auth)

    def test_preflight_not_logged_in_explains_and_offers_sample(self):
        with mock.patch.dict(os.environ, {"STUB_LOGGED_IN": "0"}):
            pf = real.preflight()
        self.assertFalse(pf.ok)
        self.assertIn("--mode sample", pf.reason)

    def test_preflight_missing_cli(self):
        with mock.patch.dict(os.environ, {real.CLAUDE_BIN_ENV: ""}), mock.patch("shutil.which", return_value=None):
            pf = real.preflight()
        self.assertFalse(pf.ok)
        self.assertIn("claude", pf.reason)

    def test_env_credential_is_detected_but_never_returned(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-" + "ant-TEST-NOT-REAL-000000"}, clear=False):
            pf = real.preflight()
        self.assertTrue(pf.ok)
        self.assertNotIn("sk-" + "ant", pf.auth + pf.reason + pf.version)

    def test_command_shape(self):
        rr = real.RealRun(project=self.tmp / "real" / "toy", info_path=self.tmp / "real" / "info.json")
        cmd = rr.command("claude", "do it")
        self.assertEqual(cmd[:3], ["claude", "-p", "do it"])
        for flag in ("--permission-mode", "--allowedTools", "--max-budget-usd", "--output-format"):
            self.assertIn(flag, cmd)
        self.assertNotIn("--bare", cmd)                      # --bare would skip the hooks Autoharness relies on
        self.assertNotIn("--dangerously-skip-permissions", cmd)
        self.assertNotIn("--no-session-persistence", cmd)    # Autoharness reads the saved transcript

    def test_end_to_end_with_stub(self):
        rr = real.RealRun(project=self.tmp / "real" / "toy", info_path=self.tmp / "real" / "info.json",
                          quiet_s=1, drain_timeout_s=10, log=lambda *_: None)
        store = rr.execute(real.load_scenarios(2))
        self.assertTrue(rr.pinned_ok)
        info = json.loads(rr.info_path.read_text())
        self.assertEqual(len(info["sessions"]), 2)
        self.assertTrue(all(s["ok"] for s in info["sessions"]))
        settings = json.loads((rr.project / ".claude" / "settings.json").read_text())
        self.assertEqual(settings["env"]["AUTOHARNESS_CAPACITY_PROJECT"], "2")
        self.assertEqual([s.name for s in store.skills()], ["stub-skill"])
        html = report.render(Store(rr.project), mode="real", note=real.report_note(rr.info_path))
        self.assertNotIn("SAMPLE / EXAMPLE DATA", html)
        self.assertEqual(report.leaks(html), [])

    def test_pin_mismatch_is_fatal(self):
        bad = {"version": 2, "plugins": {load_pin()["plugin_id"]: [{"gitCommitSha": "0" * 40}]}}
        (self.tmp / "cfg" / "plugins" / "installed_plugins.json").write_text(json.dumps(bad))
        rr = real.RealRun(project=self.tmp / "real" / "toy", info_path=self.tmp / "real" / "info.json", log=lambda *_: None)
        with self.assertRaises(real.RealUnavailable):
            rr.execute(real.load_scenarios(1))

    def test_scenarios_are_wellformed(self):
        sc = real.load_scenarios()
        self.assertGreaterEqual(len(sc), 5)
        self.assertEqual(len({s["id"] for s in sc}), len(sc))
        self.assertTrue(all(s["prompt"] and s["title_ar"] for s in sc))


if __name__ == "__main__":
    unittest.main()
