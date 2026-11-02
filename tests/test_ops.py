import unittest

from autoharness_lab import ops
from autoharness_lab.store import Store
from tests.helpers import SampleStoreCase


def capture():
    lines = []
    return lines, lines.append


class OpsTests(SampleStoreCase):
    def test_where_mentions_every_location_and_size(self):
        lines, out = capture()
        ops.cmd_where(self.store, out)
        text = "\n".join(lines)
        for needle in (".claude/skills", ".archive", "autoharness", ".ledger.jsonl", ".sidecar.json", "KB"):
            self.assertIn(needle, text)

    def test_list_and_show(self):
        lines, out = capture()
        self.assertEqual(ops.cmd_list(self.store, out=out), 0)
        self.assertIn("sample-testing-conventions", "\n".join(lines))
        lines, out = capture()
        self.assertEqual(ops.cmd_show(self.store, "sample-run-unittest-quietly", evidence=True, out=out), 0)
        text = "\n".join(lines)
        self.assertIn("[patch]", text)
        self.assertIn("نص الدليل", text)
        self.assertEqual(ops.cmd_show(self.store, "nope", out=lambda *_: None), 1)

    def test_archive_then_restore_roundtrip(self):
        name = "sample-slugify-unicode-normalization"
        self.assertEqual(ops.cmd_delete(self.store, name, yes=True, out=lambda *_: None), 0)
        self.assertFalse((self.project / ".claude/skills" / name).exists())
        self.assertTrue((self.project / ".claude/skills/.archive" / name / ".ledger.jsonl").exists())  # history kept
        self.assertEqual(ops.cmd_restore(Store(self.project), name, out=lambda *_: None), 0)
        self.assertTrue((self.project / ".claude/skills" / name / "SKILL.md").exists())

    def test_hard_delete_needs_confirmation(self):
        name = "sample-testing-conventions"
        self.assertEqual(ops.cmd_delete(self.store, name, hard=True, out=lambda *_: None), 1)  # no tty, no --yes
        self.assertTrue((self.project / ".claude/skills" / name).exists())
        self.assertEqual(ops.cmd_delete(self.store, name, hard=True, yes=True, out=lambda *_: None), 0)
        self.assertFalse((self.project / ".claude/skills" / name).exists())

    def test_unmanaged_skill_is_protected(self):
        d = self.project / ".claude/skills/mine"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: mine\ndescription: Use when x.\n---\nB\n", encoding="utf-8")
        self.assertEqual(ops.cmd_delete(Store(self.project), "mine", yes=True, out=lambda *_: None), 1)
        self.assertTrue(d.exists())

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            ops.cmd_delete(self.store, "../../etc", yes=True, out=lambda *_: None)

    def test_export_is_clean_snapshot(self):
        dest = self.tmp / "shared"
        names = ops.export_skills(self.store, dest)
        self.assertEqual(sorted(names), ["sample-run-unittest-quietly", "sample-slugify-unicode-normalization", "sample-testing-conventions"])
        for n in names:
            self.assertTrue((dest / n / "SKILL.md").exists())
            self.assertFalse((dest / n / ".ledger.jsonl").exists())
            self.assertFalse((dest / n / ".sidecar.json").exists())
            self.assertEqual(list((dest / n).rglob("evidence-*")), [])
        self.assertFalse((dest / "sample-node-18-note").exists())  # archived are not exported

    def test_export_refuses_destination_inside_skills_dir(self):
        with self.assertRaises(ValueError):
            ops.export_skills(self.store, self.project / ".claude/skills/sub")

    def test_edit_print_path(self):
        lines, out = capture()
        self.assertEqual(ops.cmd_edit(self.store, "sample-testing-conventions", print_path=True, out=out), 0)
        self.assertTrue(lines[0].endswith("sample-testing-conventions/SKILL.md"))


if __name__ == "__main__":
    unittest.main()
