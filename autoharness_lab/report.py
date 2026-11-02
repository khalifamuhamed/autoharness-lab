"""Render the Arabic (RTL) HTML report from an Autoharness store. Self-contained: no JS, no web fonts,
no network. All data read from disk is HTML-escaped (skill text is model-written, so it is untrusted)."""
from __future__ import annotations

import html
import re
from pathlib import Path

from . import __version__, sample
from .paths import SAMPLE_MARKER, load_pin
from .store import Event, Store, build_events, human_size, rejected_proposals

e = html.escape

KIND_AR = {
    "created": ("أُنشئت", "created", "مهارة جديدة تعلّمها Autoharness من الجلسة"),
    "updated": ("حُدِّثت", "updated", "تعديل مهارة موجودة بدل إنشاء نسخة مكررة"),
    "merged": ("دُمجت", "merged", "طُويت في مهارة شاملة؛ دمج وليس موتًا"),
    "pruned": ("قُلِّمت (حذف متعمّد)", "pruned", "أُرشفت بقرار صريح مع سبب مسجّل"),
    "pruned_auto": ("قُلِّمت (آليًا)", "pruned", "أرشفتها دورة الحياة تلقائيًا؛ لا يوجد سطر في السجل"),
    "file_removed": ("حُذف ملف مساند", "updated", "إزالة ملف داخل مجلد المهارة"),
}

FINDING_AR = {
    "description": "الوصف أطول من الحد المسموح به",
    "trigger": "الوصف بلا عبارة تشغيل واضحة (متى تُستخدم المهارة)",
    "structure": "خلل في بنية الملف (frontmatter أو مراجع مفقودة)",
    "files": "مشكلة في الملفات المساندة",
    "category": "تصنيف غير صالح",
    "safety": "رُفضت لأسباب أمان",
    "secret": "اشتبه بوجود سرّ (مفتاح/توكن) في المحتوى",
    "completeness": "محتوى ناقص (TODO أو نص بديل)",
    "altitude": "النص طويل جدًا؛ يجب أن يكون قاعدة لا نسخة من المحادثة",
    "global_repo_agnostic": "مهارة عامة تحوي تفاصيل خاصة بمستودع معيّن",
    "led": "ينقصها السبب أو الدليل في السجل",
    "self_produced": "تستهدف مهارة لم يكتبها Autoharness",
    "routing": "تعذّر تحديد الطبقة أو الاسم",
    "shape": "شكل الطلب غير صالح",
    "absorbed_into": "اسم المهارة الشاملة في الدمج غير صالح",
    "landing": "فشل الكتابة على القرص",
    "crash": "خطأ داخلي أثناء الفحص",
}

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2430;--mut:#5b6678;--line:#e1e5ec;--ok:#1f7a4d;--warn:#9a5b00;--bad:#b3261e;--acc:#2456d6}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 "Segoe UI",Tahoma,"Noto Naskh Arabic","Noto Sans Arabic",Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 56px}
h1{font-size:1.7rem;margin:.2rem 0}h2{font-size:1.25rem;margin:2rem 0 .6rem;border-bottom:2px solid var(--line);padding-bottom:.3rem}
h3{font-size:1.05rem;margin:.2rem 0}
.sub{color:var(--mut);margin:0 0 1rem}
.banner{border-radius:10px;padding:14px 16px;margin:12px 0;font-weight:600}
.banner.sample{background:#fff4d6;border:2px solid #e6a700;color:#5c3d00}
.banner.real{background:#e3f6ec;border:2px solid #2aa36b;color:#0f4a2e}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.stat b{display:block;font-size:1.6rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:10px 0}
.tag{display:inline-block;border-radius:999px;padding:0 10px;font-size:.85rem;font-weight:700;margin-inline-start:6px;color:#fff}
.tag.created{background:var(--ok)}.tag.updated{background:var(--acc)}.tag.merged{background:#6b3fc4}.tag.pruned{background:var(--bad)}
.ev{border-inline-start:4px solid var(--line);padding:4px 12px;margin:8px 0}
.ev.created{border-color:var(--ok)}.ev.updated{border-color:var(--acc)}.ev.merged{border-color:#6b3fc4}.ev.pruned{border-color:var(--bad)}
blockquote{margin:6px 0;padding:6px 10px;background:#f1f3f7;border-radius:6px;direction:ltr;text-align:left;font-size:.93rem;white-space:pre-wrap}
.ar{color:var(--mut);font-size:.95rem}
code,.mono{font-family:ui-monospace,Menlo,Consolas,monospace;direction:ltr;unicode-bidi:isolate;display:inline-block;font-size:.88rem;background:#eef0f5;padding:0 5px;border-radius:4px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top;font-size:.93rem}th{background:#eef1f6}
.small{font-size:.85rem;color:var(--mut)}
footer{margin-top:2.5rem;border-top:2px solid var(--line);padding-top:12px;color:var(--mut);font-size:.9rem}
a{color:var(--acc)}
"""


def _rel(skill, base: Path) -> str:
    """Display path relative to the project, never an absolute box path."""
    try:
        return skill.path.relative_to(base).as_posix()
    except ValueError:
        return f".claude/skills/{skill.name}"


def _reason_block(ev: Event, ar: str | None) -> str:
    out = ""
    if ev.reason:
        out += f'<blockquote dir="ltr" lang="en">{e(ev.reason)}</blockquote>'
    elif ev.derived:
        out += ""
    if ar:
        out += f'<div class="ar">ترجمة توضيحية للمثال: {e(ar)}</div>'
    return out


def render(store: Store, *, mode: str, note: str = "") -> str:
    """mode: 'sample' or 'real'."""
    pin = load_pin()
    is_sample = mode == "sample" or (store.project_dir / ".claude" / SAMPLE_MARKER).exists()
    events = build_events(store)
    ar_notes = sample.load_ar(store.project_dir) if is_sample else {}
    skills = store.skills(managed_only=True)
    by_name = {s.name: s for s in skills}
    runs_rej = rejected_proposals(store)
    counts = {k: sum(1 for ev in events if ev.kind == k) for k in KIND_AR}
    pruned_total = counts["pruned"] + counts["pruned_auto"]
    sizes = store.sizes()[0]

    parts: list[str] = []
    a = parts.append
    a('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a("<title>تقرير مهارات Autoharness</title>")
    a(f"<style>{CSS}</style></head><body><main>")
    a("<h1>تقرير المهارات التي أنشأها Autoharness</h1>")
    a('<p class="sub">ما الذي أنشأه Autoharness ودمجه وحدّثه وقلّمه، ولماذا؟ مأخوذ من «سجل الأسباب» (ledger) الذي يحفظه على القرص.</p>')
    if is_sample:
        a('<div class="banner sample" role="note">⚠️ <b>بيانات مثال (SAMPLE / EXAMPLE DATA)</b> — هذا التقرير مبني على بيانات توضيحية '
          "مولَّدة دون اتصال بالإنترنت، <u>ولم تنتج من جلسات Claude حقيقية</u>. أسماء المهارات تبدأ بـ <code>sample-</code>. "
          "لتشغيل حقيقي: سجّل الدخول إلى Claude Code ثم نفّذ <code>python -m autoharness_lab demo --mode real</code>.</div>")
    else:
        a('<div class="banner real">✅ <b>بيانات حقيقية</b> — أُنتجت من جلسات Claude Code الفعلية التي شغّلتها هذه الأداة على المستودع التجريبي.'
          f"{' ' + e(note) if note else ''}</div>")

    a('<h2>الملخص</h2><div class="cards">')
    for label, n in (("مهارات أُنشئت", counts["created"]), ("تحديثات", counts["updated"] + counts["file_removed"]),
                     ("دمج", counts["merged"]), ("تقليم", pruned_total),
                     ("مقترحات مرفوضة", len(runs_rej)), ("مهارات نشطة الآن", sum(1 for s in skills if not s.archived))):
        a(f'<div class="stat"><b>{n}</b>{e(label)}</div>')
    a("</div>")

    if not events:
        a('<div class="card">لم يُسجّل Autoharness أي مهارة بعد. هذا طبيعي إذا كانت الجلسات قصيرة؛ '
          "عدد استدعاءات الأدوات لم يبلغ حدّ التأمل (<code>AUTOHARNESS_REFLECT_EVERY_N</code>) أو لم تكتمل عملية التأمل في الخلفية.</div>")

    a("<h2>قصة كل مهارة</h2>")
    ordered = sorted(skills, key=lambda s: (int(s.sidecar.get("anchor", 0) or 0), s.name))
    for sk in ordered:
        status = "مؤرشفة" if sk.archived else "نشطة"
        a(f'<div class="card"><h3><span class="mono">{e(sk.name)}</span> <span class="small">({e(sk.category)} · {status})</span></h3>')
        a(f'<div class="small" dir="ltr" lang="en">{e(sk.description)}</div>')
        idx = 0
        for ev in [x for x in events if x.skill == sk.name]:
            label, css, expl = KIND_AR[ev.kind]
            ar = ar_notes.get((sk.name, idx)) if not ev.derived else None
            if not ev.derived:
                idx += 1
            extra = ""
            if ev.kind == "merged":
                extra = f' ← دُمجت في <span class="mono">{e(ev.absorbed_into)}</span>'
            if ev.kind == "file_removed" and ev.detail:
                extra = f' <span class="mono">{e(ev.detail)}</span>'
            a(f'<div class="ev {css}"><span class="tag {css}">{label}</span> <span class="small">{e(expl)}</span>{extra}')
            a(_reason_block(ev, ar))
            if ev.derived:
                s = sk.sidecar
                why = ("لم تُستخدم ولم تُعرض طوال فترة التجربة (مراجعة التخرّج)" if not s.get("use") and not s.get("view")
                       else "تجاوزت الطبقة سعتها فخرجت المهارة ذات أقل معدل استخدام")
                a(f'<div class="ar">لا يوجد سبب مكتوب في السجل لأن القرار آلي. استنتاج التقرير من العدّادات '
                  f'(use={int(s.get("use", 0))}، view={int(s.get("view", 0))}): {e(why)}.</div>')
            if ev.evidence:
                a(f'<div class="small">الدليل: <span class="mono">{e(ev.evidence)}</span></div>')
            a("</div>")
        a("</div>")

    if runs_rej:
        a("<h2>مقترحات رُفضت</h2><p class=\"sub\">يرفض «المُروِّج» (promoter) أي مقترح لا يستوفي الشروط، ويسجّل السبب في ملف التشغيل <code>runs/&lt;id&gt;.json</code>.</p>")
        a("<table><tr><th>الإجراء</th><th>المهارة</th><th>سبب الرفض</th><th>التشغيل</th></tr>")
        for r in runs_rej:
            fam = "؛ ".join(f"{FINDING_AR.get(f, f)} (<code>{e(str(f))}</code>)" for f in r["findings"]) or "—"
            a(f'<tr><td>{e(str(r["action"]))}</td><td class="mono">{e(str(r["name"]))}</td><td>{fam}</td><td class="mono small">{e(r["run"])}</td></tr>')
        a("</table>")

    a("<h2>جدول المهارات</h2><table><tr><th>المهارة</th><th>الحالة</th><th>use / view / patch</th><th>سطور السجل</th><th>الحجم</th><th>المكان</th></tr>")
    for sk in ordered:
        s = sk.sidecar
        a(f'<tr><td class="mono">{e(sk.name)}</td><td>{"مؤرشفة" if sk.archived else "نشطة"}</td>'
          f'<td class="mono">{int(s.get("use", 0))} / {int(s.get("view", 0))} / {int(s.get("patch", 0))}</td>'
          f"<td>{len(sk.ledger)}</td><td>{human_size(sk.size_bytes)}</td>"
          f'<td class="mono small">{e(_rel(sk, store.project_dir))}</td></tr>')
    a("</table>")
    a(f'<p class="small">الحجم الكلي: مهارات نشطة {human_size(sizes["skills_bytes"])} · مؤرشفة {human_size(sizes["archived_bytes"])} · '
      f'ملفات الحالة {human_size(sizes["state_bytes"])}. عدّاد الطلبات: {store.request_count()}.</p>')

    a("<h2>كيف تعرض هذه الملفات أو تعدّلها أو تحذفها</h2><div class=\"card\"><ul>")
    for cmd, what in (("python -m autoharness_lab where", "أين تُخزَّن الملفات وكم حجمها"),
                      ("python -m autoharness_lab list", "قائمة المهارات"),
                      ("python -m autoharness_lab show &lt;اسم&gt;", "عرض مهارة وسجلّها"),
                      ("python -m autoharness_lab edit &lt;اسم&gt;", "فتح المهارة في المحرّر"),
                      ("python -m autoharness_lab delete &lt;اسم&gt;", "أرشفة (قابلة للتراجع) أو <code>--hard</code> للحذف النهائي")):
        a(f"<li><code>{cmd}</code> — {what}</li>")
    a("</ul></div>")

    a(f'<footer>تقرير مولَّد بواسطة <b>autoharness-lab</b> v{e(__version__)} — مشروع تجريبي شخصي لـ muhamed khalifa مبني فوق '
      f'<a href="{e(pin["upstream"])}">Autoharness</a> من Tigerless Labs (ترخيص MIT). '
      f'النسخة المثبّتة: <span class="mono">{e(pin["plugin_version"])}</span> / <span class="mono">{e(pin["commit"][:7])}</span>. '
      "هذا المستودع ليس المشروع الرسمي ولا يحتوي على شيفرته.</footer>")
    a("</main></body></html>")
    return "\n".join(parts)


def write(store: Store, out: Path, *, mode: str, note: str = "") -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(store, mode=mode, note=note), encoding="utf-8")
    return out


_ABS_PATH = re.compile(r"(?:/workspace|/home|/Users|/root|/tmp|/var|[A-Za-z]:\\\\)[/\\\\][^\s\"'<>]*")


def leaks(text: str) -> list[str]:
    """Absolute filesystem paths or secret-looking tokens in rendered output (should be empty)."""
    found = _ABS_PATH.findall(text)
    found += re.findall(r"sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}", text)
    return found
