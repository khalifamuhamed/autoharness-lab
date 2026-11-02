"""Helper commands for the files Autoharness leaves behind: where / list / show / edit / delete /
restore / export. All of them only touch skill folders inside the resolved store."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .store import Skill, Store, check_name, human_size

EVIDENCE_GLOB = "evidence-*"
SHARE_DIRS = ("references", "templates", "scripts", "assets")


def _tilde(p: Path) -> str:
    try:
        return "~/" + p.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(p)


# ---------------------------------------------------------------- where -------------------------
def cmd_where(store: Store, out=print) -> int:
    out(f"المشروع: {store.project_dir}" + (f"   [{store.label}]" if store.label else ""))
    for row, lyr in zip(store.sizes(), store.layers):
        title = "الطبقة: مشروع (project)" if lyr.name == "project" else "الطبقة: عامة (global)"
        out(f"\n== {title} ==")
        out(f"  المهارات النشطة   : {lyr.skills_dir}   ({row['skills']} مهارة، {human_size(row['skills_bytes'])})")
        out(f"  المؤرشفة (قابلة للاسترجاع): {lyr.archive_dir}   ({row['archived']} مهارة، {human_size(row['archived_bytes'])})")
        out(f"  حالة Autoharness   : {lyr.state_dir}   ({row['state_files']} ملف، {human_size(row['state_bytes'])})")
        out("     └ runs/<id>.json = ما اقتُرح وما قُبل وما رُفض، last_run.json، requests، intents/، snapshots/")
        out(f"  سجل الأسباب (ledger): داخل كل مهارة: {lyr.skills_dir}/<اسم>/.ledger.jsonl")
        out(f"  عدّادات الاستخدام    : {lyr.skills_dir}/<اسم>/.sidecar.json  (ملفات مخفية: استخدم ls -a)")
    out("\nالطبقة العامة الحقيقية في Claude Code هي ~/.claude (أو AUTOHARNESS_GLOBAL_ROOT)؛ لا تُعرض هنا إلا بخيار --global.")
    out("حدود الحجم من Autoharness: نص SKILL.md ≤ 25 سطرًا غير فارغ، الوصف ≤ 1024 حرفًا، الدليل ≤ 200KB لكل نافذة التقاط.")
    return 0


# ---------------------------------------------------------------- list --------------------------
def cmd_list(store: Store, *, show_all: bool = False, out=print) -> int:
    skills = store.skills(managed_only=not show_all)
    if not skills:
        out("لا توجد مهارات بعد. (جرّب: python -m autoharness_lab demo)")
        return 0
    out(f"{'الاسم':42} {'الحالة':8} {'التصنيف':14} {'use/view/patch':15} {'السجل':6} الحجم")
    for sk in skills:
        s = sk.sidecar
        counters = f"{int(s.get('use', 0))}/{int(s.get('view', 0))}/{int(s.get('patch', 0))}"
        out(f"{sk.name:42} {'مؤرشفة' if sk.archived else 'نشطة':8} {sk.category[:14]:14} {counters:15} "
            f"{len(sk.ledger):<6} {human_size(sk.size_bytes)}")
    return 0


# ---------------------------------------------------------------- show --------------------------
def cmd_show(store: Store, name: str, *, evidence: bool = False, out=print) -> int:
    sk = store.find(name)
    if sk is None:
        out(f"لم أجد مهارة باسم {name!r}. استخدم list.")
        return 1
    out(f"# {sk.name}  [{'مؤرشفة' if sk.archived else 'نشطة'} · {sk.category} · طبقة {sk.layer}]")
    out(f"المسار: {sk.path}")
    out(f"الوصف: {sk.description}\n")
    out("--- SKILL.md ---")
    out((sk.path / "SKILL.md").read_text(encoding="utf-8", errors="replace").rstrip())
    out("\n--- .sidecar.json (العدّادات) ---")
    for k, v in sk.sidecar.items():
        out(f"  {k}: {v}")
    out("\n--- .ledger.jsonl (لماذا وُلدت/تغيّرت) ---")
    for i, e in enumerate(sk.ledger, 1):
        extra = f"  ← {e['absorbed_into']}" if e.get("absorbed_into") else ""
        out(f"  {i}. [{e.get('action')}]{extra}\n     السبب: {e.get('reason')}\n     الدليل: {e.get('evidence') or '—'}")
        if evidence and e.get("evidence"):
            p = sk.evidence_path(str(e["evidence"]))
            if p:
                out("     ┌── نص الدليل ──")
                for line in p.read_text(encoding="utf-8", errors="replace").rstrip().split("\n"):
                    out(f"     │ {line}")
    return 0


# ---------------------------------------------------------------- edit --------------------------
def cmd_edit(store: Store, name: str, *, print_path: bool = False, out=print) -> int:
    sk = store.find(name)
    if sk is None:
        out(f"لم أجد مهارة باسم {name!r}.")
        return 1
    target = sk.path / "SKILL.md"
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if print_path or not editor:
        out(str(target))
        if not print_path:
            out("لم يُضبط EDITOR. افتح الملف أعلاه بأي محرّر، أو نفّذ: EDITOR=nano python -m autoharness_lab edit " + name)
        return 0
    out("تنبيه: تعديلك اليدوي يبقى على القرص، لكن Autoharness قد يعدّل هذه المهارة لاحقًا لأنها من إنتاجه.")
    return subprocess.call([*shlex.split(editor), str(target)])


# ---------------------------------------------------------------- delete / restore -------------
def _confirm(question: str, assume_yes: bool, out) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        out("لا يوجد طرفية تفاعلية: أضف --yes للتأكيد.")
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes", "ن", "نعم")


def _unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stamp = time.strftime("%Y%m%dT%H%M%S")
    cand, n = dest.with_name(f"{dest.name}.{stamp}"), 2
    while cand.exists():
        cand, n = dest.with_name(f"{dest.name}.{stamp}.{n}"), n + 1
    return cand


def cmd_delete(store: Store, name: str, *, hard: bool = False, yes: bool = False, force: bool = False, out=print) -> int:
    check_name(name)
    sk = store.find(name)
    if sk is None:
        out(f"لم أجد مهارة باسم {name!r}.")
        return 1
    if not sk.managed and not force:
        out("هذه المهارة ليست من إنتاج Autoharness (لا تحمل created_by=agent)؛ لن ألمسها دون --force.")
        return 1
    if sk.path.is_symlink():
        out("المسار رابط رمزي؛ رفضت.")
        return 1
    lyr = store.layer(sk.layer)
    if hard:
        if not _confirm(f"حذف نهائي لـ {sk.name} (لا رجعة)؟", yes, out):
            out("أُلغي.")
            return 1
        shutil.rmtree(sk.path)
        out(f"حُذفت نهائيًا: {sk.name}")
        return 0
    if sk.archived:
        out("المهارة مؤرشفة أصلًا. استخدم --hard لحذفها نهائيًا.")
        return 1
    if not _confirm(f"أرشفة {sk.name} (تُنقل إلى .archive ويمكن استرجاعها)؟", yes, out):
        out("أُلغي.")
        return 1
    dest = _unique(lyr.archive_dir / sk.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(sk.path, dest)
    out(f"أُرشفت: {sk.name}  →  {dest}\nللتراجع: python -m autoharness_lab restore {sk.name}")
    return 0


def cmd_restore(store: Store, name: str, *, out=print) -> int:
    check_name(name)
    sk = store.find(name, archived=True)
    if sk is None:
        out(f"لا توجد مهارة مؤرشفة باسم {name!r}.")
        return 1
    lyr = store.layer(sk.layer)
    if (lyr.skills_dir / name).exists():
        out("يوجد بالفعل مهارة نشطة بهذا الاسم؛ لن أكتب فوقها.")
        return 1
    os.replace(sk.path, lyr.skills_dir / name)
    out(f"استُرجعت: {name}")
    return 0


# ---------------------------------------------------------------- export ------------------------
def export_skills(store: Store, dest: Path) -> list[str]:
    """Copy active Autoharness-written skills to `dest` as plain SKILL.md folders, WITHOUT the
    ledger/sidecar dotfiles or evidence slices. For tools that read the shared SKILL.md format
    (Codex, Hermes) but cannot run Autoharness itself. One-way, read-only snapshot."""
    dest = Path(dest)
    for lyr in store.layers:
        try:
            dest.resolve().relative_to(lyr.skills_dir.resolve())
            raise ValueError("الوجهة داخل مجلد المهارات نفسه؛ اختر مجلدًا آخر.")
        except ValueError as exc:
            if "الوجهة" in str(exc):
                raise
    names = []
    for sk in store.skills(archived=False, managed_only=True):
        target = dest / sk.name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        shutil.copy2(sk.path / "SKILL.md", target / "SKILL.md")
        for sub in SHARE_DIRS:
            src = sk.path / sub
            if src.is_dir():
                for f in sorted(src.rglob("*")):
                    if f.is_file() and not f.is_symlink() and not (sub == "references" and f.name.startswith("evidence-")):
                        rel = f.relative_to(sk.path)
                        (target / rel).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, target / rel)
        names.append(sk.name)
    return names


def cmd_export(store: Store, dest: Path, out=print) -> int:
    names = export_skills(store, dest)
    out(f"صُدِّرت {len(names)} مهارة إلى {dest}")
    for n in names:
        out(f"  - {n}")
    out("هذه نسخة لقراءة أدوات أخرى (Codex / Hermes). لا تنقل السجل ولا العدّادات، ولا يشغّل أي منهما Autoharness.")
    return 0
