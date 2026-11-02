# autoharness-lab — مختبر Autoharness

> **تنبيه واضح:** هذا المستودع هو **مشروعي التجريبي الخاص (demo)** المبني **فوق** أداة
> [**Autoharness**](https://github.com/tigerless-labs/autoharness) من **Tigerless Labs** (ترخيص **MIT**).
> هو **ليس** المشروع الرسمي، ولا يتبع أصحابه، ولا يحتوي على أي سطر من شيفرتهم. الفضل في فكرة Autoharness
> وتنفيذه لأصحابه؛ هنا فقط أداة صغيرة تشغّله وتعرض نتائجه بتقرير عربي. تفاصيل الائتمان في [NOTICE.md](NOTICE.md).

## English summary

`autoharness-lab` is a small personal demo built **on top of** [Autoharness](https://github.com/tigerless-labs/autoharness)
(by Tigerless Labs, MIT license), a Claude Code plugin that learns, merges, updates and prunes reusable skills from
real coding sessions and records why in a per-skill ledger. This repo (1) runs a few scripted headless Claude Code
sessions on a toy repo with the **pinned** plugin installed (plugin v0.5.3, commit `92015c0`), and (2) renders an
**Arabic RTL HTML report** of the skills created / merged / updated / pruned, with the ledger reasons.
Real mode needs a Claude login or API key. Without one, an **offline sample mode** produces the same report from
clearly labelled **example data**. It also ships helper commands (`where`, `list`, `show`, `edit`, `delete`,
`restore`, `export`) and honest integration notes: Autoharness runs on **Claude Code only**; for Codex and Hermes
the closest real option is sharing the generated `SKILL.md` files. Nothing from upstream is vendored. No secrets are stored.

---

## ١) ما هو Autoharness؟ (شرح مبسّط)

تخيّل أن معك مساعدًا يعمل بجانبك في المطبخ، ويحمل **دفتر وصفات**:

- كلما نجحتم في شيء جديد (مثلاً: «طريقة تشغيل الاختبارات في هذا المشروع»)، يكتب لها **بطاقة وصفة** قصيرة. هذه هي **المهارة (skill)**.
- إن وجد بطاقتين لنفس الأمر، **يدمجهما** في بطاقة واحدة بدل تكديس نسخ متشابهة.
- إن صحّحتَ له خطأ، **يعدّل البطاقة نفسها** ولا يكتب بطاقة جديدة.
- البطاقة التي لا يستخدمها أحد لفترة، **يضعها في درج الأرشيف** (لا يرميها؛ تستطيع إرجاعها).
- وخلف كل بطاقة **ورقة «لماذا كتبتها؟»** وهي **السجل (ledger)**: السبب + مقتطف من الجلسة كدليل.
- ولا يلمس إلا البطاقات التي كتبها بنفسه؛ بطاقاتك أنت لا يقترب منها.

**تقنيًا (حسب وثائقه):** Autoharness إضافة (plugin) لـ **Claude Code**. تراقب الجلسات عبر خطّافات (hooks)؛ بعد عدد معيّن من
استدعاءات الأدوات (الافتراضي 50) تُشغّل «مُتأمِّلًا» (reflector) في الخلفية يقترح: إنشاء / دمج / تعديل / حذف. ثم «مُروِّج» (promoter)
حتمي يفحص الاقتراح (بنية، أمان، سرّية، سبب ودليل) ولا يكتب إلا ما نجح. «المعالج الدوري» (curator) يدمج المتشابه في المكتبة كلها.
دورة الحياة تُحسب بمعدل **الاستخدام الفعلي** لا بالزمن: مهارة جديدة في «فترة تجربة»، وبعدها تُؤرشف إن لم تُستخدم ولم تُعرض أبدًا،
أو إن زادت المهارات عن السعة فتخرج الأقل استخدامًا. كل شيء يُحفظ كملفات عادية على القرص.

## ٢) ماذا تفعل هذه الأداة؟

1. **تشغّل جلسات Claude Code بلا واجهة** (`claude -p`) مكتوبة مسبقًا على مستودع تجريبي صغير (`slugkit`) مع تثبيت Autoharness المثبّت.
2. **تقرأ** ما تركه Autoharness على القرص (المهارات والسجل وحسابات التشغيل).
3. **تكتب تقريرًا عربيًا (HTML، من اليمين لليسار)** يوضح ما أُنشئ ودُمج وحُدِّث وقُلِّم ولماذا، مع المقترحات المرفوضة.
4. تعطيك **أوامر مساعدة** لمعرفة أماكن الملفات وعرضها وتعديلها وحذفها.

**شاهد مثالًا جاهزًا:** [`docs/sample-report.ar.html`](docs/sample-report.ar.html) — ⚠️ بيانات **مثال** موسومة، ليست من جلسات حقيقية.

## ٣) التشغيل السريع

المتطلبات: Python **3.11+** فقط (لا توجد حزم pip مطلوبة).

```bash
git clone <رابط-المستودع> autoharness-lab && cd autoharness-lab
python -m autoharness_lab demo        # أو: make demo
```

الأمر الواحد `demo` يختار تلقائيًا:

| الحالة | ما يحدث |
|---|---|
| `claude` مثبّت **ومسجَّل الدخول** (أو `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` موجود) | **تشغيل حقيقي**، ثم تقرير في `runtime/report.real.ar.html` |
| غير ذلك | **وضع بيانات المثال** مع تنبيه واضح، ثم تقرير في `runtime/report.sample.ar.html` |

أوامر أخرى: `python -m autoharness_lab demo --mode real|sample` · `doctor` (هل التشغيل الحقيقي جاهز؟) · `check` (فحوصات ذاتية) · `report`.

## ٤) الحقيقي مقابل بيانات المثال — بصراحة

- **الوضع الحقيقي** يحتاج حسابًا يدفع للنموذج. الأداة تقرأ الاعتماد من بيئتك أو من تسجيل دخول Claude؛ **لا تخزّن مفتاحًا ولا تكتبه في أي ملف.**
  تُثبّت الإضافة على مستوى المشروع التجريبي، وتخفض عتبات Autoharness (`REFLECT_EVERY_N=3`، `MATURITY_PROJECT=5`، `CAPACITY_PROJECT=2`، `CONSOLIDATE_EVERY_N=4`) ليظهر
  الإنشاء والدمج والتقليم خلال 7 جلسات قصيرة، وتعطّل الطبقة العامة (`AUTOHARNESS_DISABLE_GLOBAL=1`) فلا تُكتب مهارات في `~/.claude`.
  لكل جلسة سقف تكلفة (`--max-budget-usd`، الافتراضي 1$)؛ وتذكّر أن كل «تأمّل» يشغّل جلسات خلفية إضافية تستهلك رموزًا.
  ما يتعلّمه Autoharness فعليًا **غير حتمي**: قد لا تُنشأ مهارات، وهذا يظهر في التقرير كما هو.
- **وضع المثال** يبني مخزنًا وهميًا **بنفس صيغة ملفات Autoharness** (راجع [docs/FORMATS.md](docs/FORMATS.md)) لتعمل الواجهة دون أي اتصال.
  تحقّقنا مرة واحدة (خارج المستودع) أن مهارات المثال النشطة تجتاز فاحص Autoharness الأصلي وأن تصنيف الدمج/التقليم يطابق حساباته (انظر آخر docs/FORMATS.md).
  كل شيء فيه موسوم: أسماء تبدأ بـ `sample-`، ملف `SAMPLE_DATA.txt`، ولافتة صفراء بارزة في التقرير. أُضيفت ترجمة عربية توضيحية لأسباب السجل في المثال فقط.
  **لا تعتمد عليه كدليل على جودة Autoharness.**
- أسباب السجل في التشغيل الحقيقي تُعرض **كما كتبها Autoharness** (غالبًا بالإنجليزية)، دون ترجمة مخترعة.

> ملاحظة صدق: عند بناء هذا المشروع لم يكن على الجهاز تسجيل دخول Claude، لذلك **لم يُجرَّب التعلّم الحقيقي**. الذي جُرّب فعلًا مع `claude` الحقيقي (v2.1.316):
> `plugin validate` و`marketplace add` و`plugin install` للإضافة المثبّتة، والتأكد أن Claude سجّل `gitCommitSha` مطابقًا. بقية المسار الحقيقي مغطّى باختبارات
> «سباكة» بأداة `claude` وهمية (`tests/fake_claude.py`) تثبت أن الأوامر والانتظار وكتابة التقرير صحيحة فقط.

## ٥) التثبيت والإصدار المثبّت (Pinned)

**Autoharness ليس حزمة pip.** لا يوجد فيه `pyproject.toml`؛ وحزمة PyPI التي اسمها `autoharness` مشروع **مختلف لا علاقة له** — لا تثبّتها.
يُثبَّت كإضافة Claude Code. لتثبيت الإصدار، يعلن هذا المستودع «سوقًا» (marketplace) صغيرًا فيه مدخل واحد يثبّت **الـ commit بعينه**:

| البند | القيمة |
|---|---|
| إصدار الإضافة (plugin.json) | `0.5.3` (لا توجد وسوم git بعد `v0.2.5`، لذلك نثبّت الـ commit) |
| commit | `92015c0b2583072d892b54ab83352ad3490c0a7f` |
| معرّف الإضافة | `autoharness@autoharness-lab-pins` |
| ملفات التصريح | [`autoharness.pin.json`](autoharness.pin.json) · [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) · جدول `[tool.autoharness-lab.external-dependency]` في `pyproject.toml` |

```bash
claude plugin marketplace add ./autoharness-lab
claude plugin install autoharness@autoharness-lab-pins --scope project
claude plugin list        # يجب أن ترى: Version: 0.5.3
```

يتحقق الفحص الذاتي من تطابق التصريحات الثلاثة، ومن أن `dependencies` في pyproject لا تحوي `autoharness`، ومن عدم وجود شيفرته في المستودع.

## ٦) أين يخزّن Autoharness مهاراته وسجلّه؟ وكيف أعرضها/أعدّلها/أحذفها؟

كلها **ملفات عادية** (بعضها مخفي؛ استعمل `ls -a`):

| الشيء | المكان (طبقة المشروع) | ملاحظة |
|---|---|---|
| المهارة | `<المشروع>/.claude/skills/<الاسم>/SKILL.md` | تُقرأ تلقائيًا من Claude Code كأي مهارة |
| **السجل (ledger)** | `<المشروع>/.claude/skills/<الاسم>/.ledger.jsonl` | سطر JSON لكل حدث: `action` + `reason` + `evidence` |
| الدليل | `…/<الاسم>/references/evidence-*.md` | مقتطف منقّح (redacted) من الجلسة |
| عدّادات الاستخدام | `…/<الاسم>/.sidecar.json` | `use` / `view` / `patch` |
| الأرشيف | `<المشروع>/.claude/skills/.archive/<الاسم>/` | إعادة المجلد تُحيي المهارة |
| حالة التشغيل | `<المشروع>/.claude/autoharness/` | `runs/<id>.json` (المقبول والمرفوض)، `last_run.json`، `requests`، `intents/`، `snapshots/` |
| الطبقة العامة (إن فُعّلت) | `~/.claude/skills` و`~/.claude/autoharness` | أو `AUTOHARNESS_GLOBAL_ROOT`؛ نعطّلها في التجربة |

**الحجم:** الحدود من Autoharness: نص `SKILL.md` ≤ 25 سطرًا غير فارغ، الوصف ≤ 1024 حرفًا، وحد أقصى 100KB للنص، وكل دليل بحد التقاط 200KB.
عمليًا المهارة بضعة KB؛ في بيانات المثال نحو 1KB للمهارة الواحدة، والمعالج يحتفظ بحتى 5 لقطات (snapshots) قبل الدمج. الأرقام الفعلية لمشروعك:
`python -m autoharness_lab where`.

**أوامر المساعدة** (تعمل على بيانات المثال أو الحقيقية تلقائيًا؛ أضف `--mode real|sample` أو `--project <مسار>`):

| الهدف | الأمر | شرح |
|---|---|---|
| أين الملفات؟ وكم حجمها؟ | `python -m autoharness_lab where` | المسارات + الأحجام + عدد الملفات |
| القائمة | `python -m autoharness_lab list` | الاسم، الحالة، التصنيف، العدّادات، حجم السجل |
| عرض مهارة وسجلّها | `python -m autoharness_lab show <الاسم> [--evidence]` | النص + العدّادات + لماذا وُلدت/تغيّرت |
| تعديل | `python -m autoharness_lab edit <الاسم>` | يفتح `SKILL.md` في `$EDITOR` (أو `--print-path`) |
| حذف آمن | `python -m autoharness_lab delete <الاسم>` | **أرشفة** قابلة للتراجع (نفس آلية Autoharness) مع تأكيد |
| تراجع | `python -m autoharness_lab restore <الاسم>` | يعيدها من الأرشيف |
| حذف نهائي | `python -m autoharness_lab delete <الاسم> --hard` | لا رجعة؛ يطلب تأكيدًا أو `--yes` |
| نسخة لأدوات أخرى | `python -m autoharness_lab export <مجلد>` | مجلدات `SKILL.md` فقط (بدون سجل/عدّادات) |

الحماية: لا يلمس `delete` إلا المهارات التي كتبها Autoharness (`created_by: agent`) ما لم تستعمل `--force`، ويرفض أي اسم فيه `..` أو `/`.
يدويًا: `cat .claude/skills/<الاسم>/.ledger.jsonl` للعرض، وأي محرّر للتعديل، و`rm -r .claude/skills/<الاسم>` للحذف.
**تنبيه:** تعديلك اليدوي يبقى، لكن Autoharness قد يعدّل مهارته لاحقًا لأنها من إنتاجه. وحذف الإضافة (`claude plugin uninstall …`) **لا** يحذف المهارات التي كتبتها.

## ٧) التكامل مع الأدوات

| الأداة | هل يعمل Autoharness فيها؟ | ما المتوفر هنا |
|---|---|---|
| **Claude Code** | ✅ نعم (الأساسي) | [`integrations/claude-code/`](integrations/claude-code/README.md): خطوات التثبيت المثبّت، قالب `settings.project.json`، متغيرات `AUTOHARNESS_*` |
| **Codex (OpenAI)** | ❌ لا. Autoharness يعمل على Claude Code فقط ("Today it runs on Claude Code") | [`integrations/codex/`](integrations/codex/README.md): **أقرب بديل حقيقي** = تصدير المهارات (`export`) إلى `.agents/skills` + `AGENTS.md.example`. بلا تعلّم تلقائي داخل Codex |
| **Hermes Agent** | ❌ لا، وHermes عنده آلية مهارات خاصة به (`skill_manage`) | [`integrations/hermes/`](integrations/hermes/README.md): **أقرب بديل** = `skills.external_dirs` في `config.yaml` تشير إلى المجلد المصدَّر، مع تحذير أن المجلد قابل للكتابة |

لم نخترع ميزات: لا يوجد وضع Codex أو Hermes في Autoharness. المشاركة عبر صيغة `SKILL.md` المشتركة فقط، ونسخة المصدَّر لقطة أحادية الاتجاه.

## ٨) الفحوصات الذاتية والاختبارات

```bash
python -m autoharness_lab check              # 10 فحوصات سريعة دون إنترنت
python -m unittest discover -s tests -q      # اختبارات الوحدة (stdlib فقط)
make test                                    # الاثنان معًا
```

تشمل: اتساق التثبيت المعلن، عدم وجود شيفرة Autoharness، `.gitignore`، فحص الأسرار، خط الأنابيب (مثال ← أحداث ← تقرير عربي)، **حداثة التقرير المرفق وخلوّه من مسارات الجهاز**،
مستودع التجربة، وثائق التكامل، حقوق الائتمان في README، وهوية git.

## ٩) بنية المستودع

```
autoharness_lab/        الشيفرة: cli, store (قراءة ملفات Autoharness), report (HTML عربي), sample, real, ops, selfcheck
toy_repo_template/      مستودع slugkit التجريبي (اختبار واحد يفشل عمدًا)
integrations/           Claude Code · Codex · Hermes
docs/                   FORMATS.md + sample-report.ar.html (بيانات مثال موسومة)
.claude-plugin/         marketplace.json يثبّت commit محدّدًا من Autoharness (لا نسخ للشيفرة)
autoharness.pin.json    مصدر الحقيقة للإصدار المثبّت
tests/                  اختبارات unittest (+ claude وهمي لاختبار السباكة فقط)
runtime/                (يُولَّد، مُتجاهَل في git) المخازن والسجلات والتقارير
```

## ١٠) الأمان والخصوصية

- لا أسرار في المستودع، و`.gitignore` يغطي `.env*` و`*.pem` و`*.key` وبيانات التشغيل والكاشات. الفحص الذاتي يبحث عن أنماط المفاتيح.
- التقرير المرفق لا يحوي مسارات مطلقة من الجهاز (تُعرض مسارات نسبية فقط).
- في التشغيل الحقيقي يُرسَل محتوى المستودع التجريبي الصغير فقط إلى Anthropic عبر Claude Code؛ وAutoharness نفسه ينقّح (redact) الأدلة قبل حفظها.
- الجلسات تعمل بصلاحيات `acceptEdits` وقائمة أدوات مسموحة محدودة (قراءة/تعديل/اختبارات unittest)، لا `--dangerously-skip-permissions` في الجلسات الرئيسية. *(Autoharness نفسه يشغّل جلساته الفرعية بهذا الخيار حسب شيفرته.)*

## ١١) قيود معروفة

- Autoharness مشروع حديث؛ الإصدار 0.5.3 بلا وسم git، وصيغ ملفاته قد تتغيّر. لذلك الـ commit مثبّت وقراءتنا للصيغ موثّقة.
- السجل لا يحوي طوابع زمنية؛ تُرتّب المهارات بنقطة إنشائها.
- «القلّم الآلي» (أرشفة دورة الحياة) لا يترك سطرًا في السجل؛ التقرير يستنتج السبب من العدّادات ويصرّح بذلك.
- لم يُختبر التعلّم الحقيقي عند البناء (لا تسجيل دخول). تأكّد بنفسك: `python -m autoharness_lab doctor` ثم `demo --mode real`.

## ١٢) نشر المستودع (خطوات لصاحب المشروع)

```bash
gh auth login                                  # تسجيل دخول بالجهاز (device login)
gh repo create khalifamuhamed/autoharness-lab --public --source . --remote origin --push
```

بعد النشر يعمل أيضًا `claude plugin marketplace add khalifamuhamed/autoharness-lab` وقالب `settings.project.json`.

## الائتمان والترخيص

- **Autoharness** © Tigerless Labs — ترخيص **MIT** — https://github.com/tigerless-labs/autoharness (مثبّت على `92015c0`).
- ملفات هذا المستودع © 2026 muhamed khalifa — ترخيص **MIT** ([LICENSE](LICENSE)). هذا مشروع شخصي مستقل، **مبني على** Autoharness وليس جزءًا منه.
