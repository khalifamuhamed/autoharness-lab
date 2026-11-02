import json
import unittest

from autoharness_lab import report
from autoharness_lab.store import Store
from tests.helpers import SampleStoreCase


class ReportTests(SampleStoreCase):
    def test_rtl_arabic_and_sample_banner(self):
        html = report.render(self.store, mode="sample")
        self.assertIn('<html lang="ar" dir="rtl">', html)
        self.assertIn("SAMPLE / EXAMPLE DATA", html)
        self.assertIn("بيانات مثال", html)
        for label in ("أُنشئت", "حُدِّثت", "دُمجت", "قُلِّمت"):
            self.assertIn(label, html)
        self.assertIn("سبب الرفض", html)
        self.assertIn("MIT", html)
        self.assertIn("Tigerless Labs", html)

    def test_no_absolute_paths_or_secrets(self):
        html = report.render(self.store, mode="sample")
        self.assertEqual(report.leaks(html), [])
        self.assertNotIn(str(self.tmp), html)

    def test_untrusted_skill_text_is_escaped(self):
        sk = self.project / ".claude/skills/sample-testing-conventions"
        (sk / "SKILL.md").write_text('---\nname: sample-testing-conventions\ndescription: "<script>alert(1)</script>"\ncategory: x\n---\nB\n', encoding="utf-8")
        ledger = sk / ".ledger.jsonl"
        ledger.write_text(json.dumps({"action": "create", "reason": "<img src=x onerror=alert(1)>", "evidence": ""}) + "\n", encoding="utf-8")
        html = report.render(Store(self.project), mode="sample")
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)

    def test_real_mode_has_no_sample_banner(self):
        (self.project / ".claude" / "SAMPLE_DATA.txt").unlink()
        html = report.render(Store(self.project), mode="real", note="ملاحظة")
        self.assertNotIn("SAMPLE / EXAMPLE DATA", html)
        self.assertIn("بيانات حقيقية", html)

    def test_empty_store_explains_itself(self):
        html = report.render(Store(self.tmp / "empty"), mode="real")
        self.assertIn("لم يُسجّل Autoharness أي مهارة", html)

    def test_leak_detector_works(self):
        self.assertTrue(report.leaks("see /home/box/x"))
        self.assertTrue(report.leaks("key sk-" + "ant-api03-aaaaaaaaaaaaaaaaaaaa"))
        self.assertFalse(report.leaks("relative .claude/skills/x"))


if __name__ == "__main__":
    unittest.main()
