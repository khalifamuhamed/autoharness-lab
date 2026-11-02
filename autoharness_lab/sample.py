"""Offline SAMPLE data generator.

Writes a fake-but-format-faithful Autoharness store (see store.py for the layout) so the report can be
rendered without any Claude login. EVERYTHING produced here is EXAMPLE data, not the output of a real
Autoharness run: skill names are prefixed `sample-`, a SAMPLE_DATA.txt marker is written, and the
report shows a prominent banner. The story below mimics the lifecycle described in Autoharness's README
(create -> update -> merge -> prune) over four scripted sessions on the toy `slugkit` repo.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .paths import SAMPLE_MARKER, SAMPLE_PROJECT

MARKER_TEXT = (
    "SAMPLE / EXAMPLE DATA - generated offline by autoharness-lab (`demo --mode sample`).\n"
    "This is NOT the output of a real Autoharness run and no Claude session produced it.\n"
    "بيانات مثال توضيحية فقط، لم تنتج من جلسات Claude حقيقية.\n"
)

RUN_TEST = "python -m unittest discover -s tests -q -f"

AR_NOTES_FILE = "sample-notes-ar.json"  # sidecar next to the marker: "skill|ledger-index" -> Arabic gloss
SAMPLE_AR: dict[tuple[str, int], str] = {}  # filled while building; persisted to AR_NOTES_FILE


def load_ar(project: Path) -> dict[tuple[str, int], str]:
    """Arabic glosses of the English SAMPLE reasons (only exist for sample data)."""
    try:
        raw = json.loads((project / ".claude" / AR_NOTES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in raw.items():
        name, _, idx = k.rpartition("|")
        out[(name, int(idx))] = v
    return out


def _ev(text: str) -> str:
    return text.strip() + "\n"


def _write_skill(root: Path, name, description, category, body, ledger, sidecar, *, archived=False):
    base = root / "skills" / (".archive" if archived else "") / name
    base.mkdir(parents=True, exist_ok=True)
    (base / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "{description}"\ncategory: {category}\n---\n{body.strip()}\n',
        encoding="utf-8")
    (base / "references").mkdir(exist_ok=True)
    lines = []
    for i, (action, reason, evidence, ar, extra) in enumerate(ledger):
        entry = {"action": action, "reason": reason}
        if evidence:
            text = _ev(evidence)
            rel = f"references/evidence-{hashlib.sha256(text.encode()).hexdigest()}.md"
            (base / rel).write_text(text, encoding="utf-8")
            entry["evidence"] = rel
        else:
            entry["evidence"] = ""
        entry.update(extra)
        lines.append(json.dumps(entry, ensure_ascii=False))
        if ar:
            SAMPLE_AR[(name, i)] = ar
    (base / ".ledger.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (base / ".sidecar.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")


def build(project: Path = SAMPLE_PROJECT) -> Path:
    """(Re)create the sample project store at `project`. Returns the project dir."""
    if project.exists():
        shutil.rmtree(project)
    root = project / ".claude"
    root.mkdir(parents=True)
    (root / SAMPLE_MARKER).write_text(MARKER_TEXT, encoding="utf-8")
    SAMPLE_AR.clear()

    def sc(use, view, patch, anchor, **kw):
        d = {"created_by": "agent", "use": use, "view": view, "patch": patch, "anchor": anchor, "verification": None}
        d.update(kw)
        return d

    # --- session 1: fix the failing unicode test -------------------------------------------------
    _write_skill(
        root, "sample-run-unittest-quietly",
        "Use when running slugkit tests or seeing 'Ran 0 tests'.",
        "testing",
        f"Run the tests with `{RUN_TEST}` from the repo root.\n\n"
        "- A bare `python -m unittest` finds nothing because tests live in `tests/`.\n"
        "- Read the first failure only; fix it, then re-run the same command.",
        [("create",
          "User had to ask twice how to run the tests; bare `python -m unittest` ran 0 tests. The working command is reusable for every task in this repo.",
          "user: why does python -m unittest say Ran 0 tests?\nassistant: tests are under tests/, use discover -s tests.\ntool: Bash `python -m unittest discover -s tests -q` -> FAILED (failures=1)",
          "المستخدم سأل مرتين عن طريقة تشغيل الاختبارات، والأمر المجرّد لم يشغّل أي اختبار. الأمر الصحيح قابل لإعادة الاستخدام في كل مهمة بالمستودع.", {}),
         ("patch",
          "User corrected the skill: stop at the first failure with -f so the output stays readable.",
          "user: that's too noisy, add -f so it stops at the first failure.\nassistant: updated command to `python -m unittest discover -s tests -q -f`.",
          "صحّح المستخدم المهارة: يجب الإيقاف عند أول فشل بإضافة -f ليبقى الإخراج مقروءًا. (تحديث للمهارة نفسها بدل إنشاء مهارة مكررة.)", {})],
        sc(7, 2, 1, 0, reused_gen=1))

    _write_skill(
        root, "sample-slugify-unicode-normalization",
        "Use when slugify output has accents or non-ASCII letters.",
        "python-text",
        "Normalize with `unicodedata.normalize('NFKD', text)` and drop combining marks before the regex pass.\n\n"
        "- Lowercase after normalizing, not before.\n- Collapse runs of separators into a single `-`.",
        [("create",
          "Failing test `test_unicode` showed that accented letters were dropped instead of transliterated; the NFKD-then-strip technique fixed it and applies to any slug helper.",
          "tool: Bash unittest -> FAIL: test_unicode ('creme-brulee' != 'crme-brle')\nassistant: normalize NFKD, strip category Mn, then regex.",
          "اختبار `test_unicode` فشل لأن الحروف المشكّلة كانت تُحذف بدل أن تُحوَّل. تقنية NFKD ثم إزالة العلامات حلّت المشكلة وتنطبق على أي دالة slug.", {})],
        sc(3, 1, 0, 0))

    _write_skill(
        root, "sample-node-18-note",
        "Use when picking a Node version for the docs build.",
        "environment",
        "The docs build targets Node 18; use `nvm use 18` before building.",
        [("create",
          "Session mentioned the docs build needs Node 18.",
          "user: docs build only works on node 18 here.",
          "ذكرت الجلسة أن بناء التوثيق يحتاج Node 18.", {}),
         ("delete",
          "Later session showed the docs build was removed from the project, so this rule is obsolete and misleading.",
          "user: we deleted the docs build last week, the toy repo is pure Python now.\nassistant: removing the Node 18 note.",
          "أظهرت جلسة لاحقة أن بناء التوثيق أُزيل من المشروع، فأصبحت القاعدة قديمة ومضلِّلة. (حذف متعمّد مع سبب مسجّل.)", {})],
        sc(0, 0, 0, 0), archived=True)

    # --- session 2: add truncate_slug ------------------------------------------------------------
    _write_skill(
        root, "sample-unittest-tempdir-fixture",
        "Use when a slugkit test needs temporary files.",
        "testing",
        "Create a `tempfile.TemporaryDirectory()` in `setUp` and register `self.addCleanup(tmp.cleanup)`.\n\n"
        "- Never write test files into the repo tree.",
        [("create",
          "New feature tests needed scratch files; the TemporaryDirectory + addCleanup pattern kept the repo tree clean.",
          "assistant: tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)\ntool: Bash unittest -> OK",
          "اختبارات الميزة الجديدة احتاجت ملفات مؤقتة، ونمط TemporaryDirectory مع addCleanup أبقى المستودع نظيفًا.", {}),
         ("delete",
          "Folded into the umbrella skill `sample-testing-conventions`: same scenario (how to write slugkit tests), so keeping two near-duplicates would only add noise.",
          "curator: sample-unittest-tempdir-fixture overlaps sample-testing-conventions -> merge.",
          "دُمجت في المهارة الشاملة `sample-testing-conventions`: نفس السيناريو (كتابة اختبارات slugkit)، وإبقاء نسختين متشابهتين يضيف ضجيجًا فقط. (هذا دمج وليس موتًا: السجل يذكر المهارة التي استوعبتها.)",
          {"absorbed_into": "sample-testing-conventions"})],
        sc(1, 0, 0, 1), archived=True)

    _write_skill(
        root, "sample-changelog-entry-format",
        "Use when adding a CHANGELOG.md entry for slugkit.",
        "docs",
        "Add one line under `## Unreleased` as `- <verb> <what> (#issue)`.",
        [("create",
          "The change request asked for a CHANGELOG line; the format was stated once.",
          "user: add a changelog line like '- Added truncate_slug (#12)'.",
          "طُلب إضافة سطر في CHANGELOG وذُكر التنسيق مرة واحدة.", {})],
        sc(0, 0, 0, 1), archived=True)

    # --- session 4: curator creates the umbrella -------------------------------------------------
    _write_skill(
        root, "sample-testing-conventions",
        "Use when writing or running tests in slugkit.",
        "testing",
        f"Tests live in `tests/`, run with `{RUN_TEST}`.\n\n"
        "- Use `tempfile.TemporaryDirectory` + `addCleanup` for scratch files.\n"
        "- One assertion theme per test method; name them `test_<behavior>`.",
        [("create",
          "Consolidation pass: several small testing skills describe one scenario (writing/running slugkit tests); created one umbrella to hold them.",
          "curator: found sample-unittest-tempdir-fixture + sample-run-unittest-quietly in the same category.",
          "مرحلة التوحيد: عدّة مهارات صغيرة تصف سيناريو واحدًا (كتابة/تشغيل اختبارات slugkit)، فأُنشئت مهارة شاملة تجمعها.", {})],
        sc(2, 1, 0, 3))

    # --- run accounts (what landed / what was rejected, per Autoharness `runs/<id>.json`) --------
    state = root / "autoharness"
    (state / "runs").mkdir(parents=True)
    (state / "requests").write_text("8", encoding="utf-8")
    runs = [
        ("sample-s1-3-a1", [("create", "sample-run-unittest-quietly", True, [], []),
                            ("create", "sample-slugify-unicode-normalization", True, [], []),
                            ("create", "sample-node-18-note", True, [], [])]),
        ("sample-s2-3-b2", [("create", "sample-unittest-tempdir-fixture", True, [], []),
                            ("create", "sample-changelog-entry-format", True, [], []),
                            ("create", "sample-fix-stuff", False, ["trigger"], [])]),
        ("sample-s3-3-c3", [("patch", "sample-run-unittest-quietly", True, [], []),
                            ("delete", "sample-node-18-note", True, [], [])]),
        ("sample-s4-c8", [("create", "sample-testing-conventions", True, [], []),
                          ("delete", "sample-unittest-tempdir-fixture", True, [], [])]),
    ]
    for rid, rows in runs:
        rec = {"run_id": rid, "verdicts": [
            {"action": a, "name": n, "ok": ok, "findings": f, "notes": notes} for a, n, ok, f, notes in rows]}
        (state / "runs" / f"{rid}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    (root / AR_NOTES_FILE).write_text(
        json.dumps({f"{n}|{i}": v for (n, i), v in SAMPLE_AR.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return project
