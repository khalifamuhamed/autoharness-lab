import json
import unittest

from autoharness_lab.store import Store, build_events, check_name, parse_frontmatter, read_jsonl, rejected_proposals
from tests.helpers import SampleStoreCase


class StoreTests(SampleStoreCase):
    def test_frontmatter(self):
        meta, body = parse_frontmatter('---\nname: x\ndescription: "Use when y."\ncategory: testing\n---\nBody\n')
        self.assertEqual(meta["description"], "Use when y.")
        self.assertEqual(meta["category"], "testing")
        self.assertEqual(body.strip(), "Body")

    def test_torn_jsonl_line_is_skipped(self):
        p = self.tmp / "l.jsonl"
        p.write_text('{"action":"create"}\n{"action":"pat', encoding="utf-8")
        self.assertEqual(read_jsonl(p), [{"action": "create"}])

    def test_unsafe_names_rejected(self):
        for bad in ("../x", "a/b", "", ".hidden", "a..b", "x y"):
            with self.assertRaises(ValueError):
                check_name(bad)

    def test_active_and_archived_split(self):
        active = {s.name for s in self.store.skills(archived=False)}
        archived = {s.name for s in self.store.skills(archived=True)}
        self.assertEqual(active, {"sample-run-unittest-quietly", "sample-slugify-unicode-normalization", "sample-testing-conventions"})
        self.assertEqual(archived, {"sample-node-18-note", "sample-unittest-tempdir-fixture", "sample-changelog-entry-format"})

    def test_unmanaged_skills_are_ignored(self):
        mine = self.project / ".claude" / "skills" / "hand-written"
        mine.mkdir()
        (mine / "SKILL.md").write_text("---\nname: hand-written\ndescription: Use when x.\n---\nBody\n", encoding="utf-8")
        self.assertNotIn("hand-written", {s.name for s in Store(self.project).skills()})
        self.assertIn("hand-written", {s.name for s in Store(self.project).skills(managed_only=False)})


class EventTests(SampleStoreCase):
    def test_event_classification_matches_upstream_rules(self):
        by = {}
        for e in build_events(self.store):
            by.setdefault((e.kind, e.skill), e)
        self.assertIn(("created", "sample-run-unittest-quietly"), by)
        self.assertIn(("updated", "sample-run-unittest-quietly"), by)
        merged = by[("merged", "sample-unittest-tempdir-fixture")]
        self.assertEqual(merged.absorbed_into, "sample-testing-conventions")
        self.assertIn(("pruned", "sample-node-18-note"), by)          # delete without absorbed_into
        auto = by[("pruned_auto", "sample-changelog-entry-format")]    # archived, no delete line
        self.assertTrue(auto.derived)
        self.assertEqual(auto.reason, "")

    def test_rejections_come_from_run_accounts(self):
        rej = rejected_proposals(self.store)
        self.assertEqual([(r["name"], r["findings"]) for r in rej], [("sample-fix-stuff", ["trigger"])])

    def test_ledger_evidence_files_exist(self):
        for sk in self.store.skills():
            for entry in sk.ledger:
                self.assertIsNotNone(sk.evidence_path(entry["evidence"]), (sk.name, entry))

    def test_sample_is_labelled_on_disk(self):
        text = (self.project / ".claude" / "SAMPLE_DATA.txt").read_text(encoding="utf-8")
        self.assertIn("SAMPLE", text)
        self.assertTrue(all(s.name.startswith("sample-") for s in self.store.skills()))
        runs = json.loads(next((self.project / ".claude" / "autoharness" / "runs").glob("*.json")).read_text())
        self.assertTrue(runs["run_id"].startswith("sample-"))


if __name__ == "__main__":
    unittest.main()
