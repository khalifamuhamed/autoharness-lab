"""Command line: `python -m autoharness_lab <command>` (run `python -m autoharness_lab --help`)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__, ops, real, report, sample, selfcheck
from .paths import REAL_PROJECT, RUNTIME, SAMPLE_PROJECT, load_pin
from .store import Store


def _global_root() -> Path:
    override = os.environ.get("AUTOHARNESS_GLOBAL_ROOT", "").strip()
    return Path(override).expanduser() if override else Path.home() / ".claude"


def resolve_store(args) -> tuple[Store, str]:
    """Pick which store the helper commands look at. Returns (store, mode)."""
    g = _global_root() if getattr(args, "global_layer", False) else None
    if getattr(args, "project", None):
        return Store(Path(args.project).expanduser().resolve(), g, label="custom"), "real"
    mode = getattr(args, "mode", "auto")
    if mode == "auto":
        has_real = (REAL_PROJECT / ".claude" / "autoharness").exists() or (REAL_PROJECT / ".claude" / "skills").exists()
        mode = "real" if has_real else "sample"
    proj = REAL_PROJECT if mode == "real" else SAMPLE_PROJECT
    label = "بيانات حقيقية" if mode == "real" else "بيانات مثال (sample)"
    if mode == "sample" and not proj.exists():
        sample.build(proj)  # cheap and offline: make `list`/`where` work out of the box
    return Store(proj, g, label=label), mode


def _add_store_args(p):
    p.add_argument("--mode", choices=("auto", "real", "sample"), default="auto", help="أي بيانات تُعرض (الافتراضي: الحقيقية إن وُجدت وإلا المثال)")
    p.add_argument("--project", help="مسار مشروع آخر يستخدم Autoharness (يقرأ <project>/.claude)")
    p.add_argument("--global", dest="global_layer", action="store_true", help="اعرض أيضًا الطبقة العامة (~/.claude)")


def cmd_demo(args) -> int:
    pin = load_pin()
    mode = args.mode
    pf = real.preflight()
    if mode == "auto":
        mode = "real" if pf.ok else "sample"
        if mode == "sample":
            print(f"[تنبيه] تعذّر التشغيل الحقيقي: {pf.reason}\n[تنبيه] سأعرض وضع «بيانات مثال» الموسوم بوضوح. هذه ليست نتائج Autoharness حقيقية.\n")
    if mode == "real":
        if not pf.ok:
            print(f"التشغيل الحقيقي غير متاح: {pf.reason}", file=sys.stderr)
            return 2
        scenarios = real.load_scenarios(args.sessions)
        try:
            store = real.RealRun(budget_usd=args.budget, log=print).execute(scenarios)
        except real.RealUnavailable as exc:
            print(f"التشغيل الحقيقي توقف: {exc}", file=sys.stderr)
            return 2
        out = Path(args.out) if args.out else RUNTIME / "report.real.ar.html"
        report.write(store, out, mode="real", note=real.report_note())
    else:
        proj = sample.build()
        store = Store(proj, label="sample")
        out = Path(args.out) if args.out else RUNTIME / "report.sample.ar.html"
        report.write(store, out, mode="sample")
    print(f"\nالتقرير ({'حقيقي' if mode == 'real' else 'بيانات مثال'}): {out}")
    print(f"Autoharness المثبّت: {pin['plugin_version']} @ {pin['commit'][:7]}")
    return 0


def cmd_report(args) -> int:
    store, mode = resolve_store(args)
    if args.out:
        out = Path(args.out)
    else:
        out = RUNTIME / f"report.{mode}.ar.html"
    note = real.report_note() if mode == "real" else ""
    report.write(store, out, mode=mode, note=note)
    print(f"كُتب التقرير: {out}")
    return 0


def cmd_sample(args) -> int:
    out = Path(args.out) if args.out else SAMPLE_PROJECT
    proj = sample.build(out)
    print(f"بُنيت بيانات المثال (SAMPLE) في: {proj}")
    return 0


def cmd_doctor(args) -> int:
    pin = load_pin()
    print(f"autoharness-lab {__version__}")
    print(f"Autoharness المثبّت : {pin['plugin_version']} @ {pin['commit']}  ({pin['upstream']})")
    print(f"معرّف الإضافة       : {pin['plugin_id']}")
    pf = real.preflight()
    print(f"claude CLI          : {pf.version or 'غير موجود'}")
    print(f"تسجيل الدخول/المفتاح : {pf.auth or 'لا يوجد'}")
    print(f"التشغيل الحقيقي      : {'جاهز ✅' if pf.ok else 'غير جاهز ❌ — ' + pf.reason}")
    sha = real.installed_commit(pin["plugin_id"])
    print(f"الإضافة مثبّتة؟      : {('نعم @ ' + sha[:7] + (' ✅ يطابق التثبيت' if sha == pin['commit'] else ' ⚠ لا يطابق')) if sha else 'لا (ستُثبَّت تلقائيًا عند التشغيل الحقيقي)'}")
    return 0 if pf.ok else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m autoharness_lab", description="مختبر Autoharness: تشغيل جلسات مبرمجة وعرض المهارات والسجل بتقرير عربي. (مشروع تجريبي شخصي مبني فوق Autoharness)")
    ap.add_argument("--version", action="version", version=f"autoharness-lab {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("demo", help="الأمر الواحد: يشغّل التجربة ويكتب التقرير العربي")
    p.add_argument("--mode", choices=("auto", "real", "sample"), default="auto")
    p.add_argument("--sessions", type=int, help="عدد الجلسات المبرمجة (الافتراضي: كلها)")
    p.add_argument("--budget", type=float, default=1.0, help="سقف التكلفة بالدولار لكل جلسة (--max-budget-usd)")
    p.add_argument("--out", help="مسار ملف HTML الناتج")
    p.set_defaults(fn=cmd_demo)

    p = sub.add_parser("report", help="اكتب تقريرًا من البيانات الموجودة"); _add_store_args(p)
    p.add_argument("--out"); p.set_defaults(fn=cmd_report)

    p = sub.add_parser("sample", help="ابنِ بيانات المثال (SAMPLE) دون اتصال"); p.add_argument("--out"); p.set_defaults(fn=cmd_sample)
    p = sub.add_parser("doctor", help="افحص الجاهزية للتشغيل الحقيقي والتثبيت المعلن"); p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("where", help="أين تُخزَّن المهارات والسجل وكم حجمها"); _add_store_args(p)
    p.set_defaults(fn=lambda a: ops.cmd_where(resolve_store(a)[0]))
    p = sub.add_parser("list", help="اعرض المهارات"); _add_store_args(p)
    p.add_argument("--all", action="store_true", help="اعرض حتى المهارات التي لم يكتبها Autoharness")
    p.set_defaults(fn=lambda a: ops.cmd_list(resolve_store(a)[0], show_all=a.all))
    p = sub.add_parser("show", help="اعرض مهارة وسجلّها"); _add_store_args(p)
    p.add_argument("name"); p.add_argument("--evidence", action="store_true", help="اعرض نص الدليل أيضًا")
    p.set_defaults(fn=lambda a: ops.cmd_show(resolve_store(a)[0], a.name, evidence=a.evidence))
    p = sub.add_parser("edit", help="افتح SKILL.md في المحرّر ($EDITOR)"); _add_store_args(p)
    p.add_argument("name"); p.add_argument("--print-path", action="store_true")
    p.set_defaults(fn=lambda a: ops.cmd_edit(resolve_store(a)[0], a.name, print_path=a.print_path))
    p = sub.add_parser("delete", help="أرشفة مهارة (قابلة للتراجع) أو حذفها نهائيًا بـ --hard"); _add_store_args(p)
    p.add_argument("name"); p.add_argument("--hard", action="store_true"); p.add_argument("--yes", action="store_true")
    p.add_argument("--force", action="store_true", help="اسمح بلمس مهارة لم يكتبها Autoharness")
    p.set_defaults(fn=lambda a: ops.cmd_delete(resolve_store(a)[0], a.name, hard=a.hard, yes=a.yes, force=a.force))
    p = sub.add_parser("restore", help="أعد مهارة مؤرشفة"); _add_store_args(p); p.add_argument("name")
    p.set_defaults(fn=lambda a: ops.cmd_restore(resolve_store(a)[0], a.name))
    p = sub.add_parser("export", help="انسخ المهارات النشطة كمجلدات SKILL.md عادية لـ Codex/Hermes"); _add_store_args(p)
    p.add_argument("dest", nargs="?", default=str(RUNTIME / "shared-skills"))
    p.set_defaults(fn=lambda a: ops.cmd_export(resolve_store(a)[0], Path(a.dest)))

    p = sub.add_parser("check", help="الفحوصات الذاتية السريعة (دون إنترنت)"); p.set_defaults(fn=lambda a: selfcheck.run_cli())
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except ValueError as exc:  # e.g. unsafe skill name
        print(f"خطأ: {exc}", file=sys.stderr)
        return 2
