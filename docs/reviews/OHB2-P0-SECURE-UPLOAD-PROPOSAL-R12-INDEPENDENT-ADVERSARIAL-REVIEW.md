# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12 — مراجعة عدائية مستقلة

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-INDEPENDENT-ADVERSARIAL-REVIEW`

المراجِع: مراجِع عدائي مستقل بسياق جديد؛ **ليس** مؤلّف مقترح r12، **وليس** مؤلّف المراجعة الذاتية R12،
**وليس** مؤلّف أي مراجعة أو مراجعة ذاتية سابقة (r2–r11). تمّ التعامل مع تقرير إكمال R12 والمراجعة الذاتية
R12 على أنهما **ادّعاءات يجب التحقّق منها**، لا أدلّة. جميع الأعمال **قراءة فقط**: أُعيد جلب المصدر العام
المثبّت (pinned) والمواصفة الحيّة بشكل مستقل في هذه الجلسة وأُعيد حساب التجزئات؛ **لا استدعاء إنتاجي، لا
اعتماد، لا وصول لأسرار، ولا تعديل** للمقترح أو المراجعة الذاتية أو `PROGRESS.md` أو الذاكرة أو الكود أو
الاختبارات أو أي مراجعة سابقة. هذا الملف هو **الأثر الوحيد** المُنشأ. لا commit/push/PR/merge/deploy، ولا
تغيير فرع، ولا تواصل مع المشرفين. **P0 لا يزال غير مُنفَّذ وغير مُعتمَد.**

## 1. الحُكم (Verdict): **`PASS_WITH_NOTES`**

r12 **يعالج الثلاث ملاحظات N11-1/N11-2/N11-3 بشكل كامل وصحيح** — أعدتُ اشتقاق كل حقيقة متنازع عليها من
المصدر المثبّت بشكل مستقل (§4)، وكل تصحيح في r12 **يطابق الحقيقة الأرضية**. لا شرط أمني ولا تخفيف لنموذج
التهديد ولا ثابت P0 تمّ إضعافه، وكل ملاحظة سابقة (N10-1…N10-3، R9-1…R9-4، R8-1…R8-4، R7-1…R7-4،
R6-1…R6-5، N-1…N-5) لا تزال مُعالَجة (§5).

لم أصدر `PASS` لأنني وجدت **عيبًا بنيويًا واحدًا غير حاجز في تنسيق Markdown** في سجل المراجعات §13
(سطر فارغ يقسم جدول المراجعات، فيُعرض صف r12 كجدول منفصل) — وهو **توثيقي بحت**، لا يغيّر أي ادّعاء تقني،
و**غير حاجز** للاعتماد. انظر §9 (N12-1).

هذا الحُكم **لا يعني** اعتماد تنفيذ P0 بأي شكل (§10).

---

## 2. خط الأساس المُتحقَّق منه (Baseline)

- **المستودع:** `/workspace/project/OpenHandBot`؛ **الفرع:** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`.
- **HEAD:** `907b20de3fa6627795c14f29677e9f39c68e82f4`؛ **`origin/main`:** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **مسار المقترح:** `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`.
  - **عدد الأسطر:** 3185. **SHA-256:** `6ea52debd62918e831555a7ea4787cde75fa62c75e376ac5df93ece33e34e4dc`.
  - يطابق **الهدف المرجعي** الذي ذكره المكلّف (`6ea52deb…e4dc`) — أُعيد حسابه فعليًا، ولم يُفترض.
- **مسار المراجعة الذاتية R12:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-SELF-REVIEW.md`.
  - **عدد الأسطر:** 96. **SHA-256:** `9e39bf033dbba0cb04ed5fb0a4c475a0ea650d6460fe26713ff4c6d009abfa99`.
  - يطابق **الهدف المرجعي** (`9e39bf03…fa99`) — أُعيد حسابه فعليًا.
- **مراجعة R11 المستقلة:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  — 258 سطرًا، sha256 `09963ded7bcc7279aabc77f99adf488fe9339686ff248b197ba367414ce6b990`.
- **مراجعة R10 المستقلة:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  — 235 سطرًا، sha256 `14d4d8a6c621abdd8d9211b4fdf08b7df2856ec21504d46fa21cdf7d18c24415`.
- **حالة الشجرة الابتدائية** (`git status --short`) — محفوظة حرفيًا كما وُجدت:

```
 M .agent/PROGRESS.md
 M bot/handlers.py
 M docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md
 M docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md
?? docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? tests/test_stage2_high_ack_blocking_fix.py
?? tests/test_stage4_f1_status_cost_operational_ack.py
```

---

## 3. جدول الاسترجاع المستقل للمصادر والتحقّق من التجزئات

أُعيد جلب كل ملف من `raw.githubusercontent.com` على الـ SHA المثبّت (أو من المواصفة الحيّة) في هذه الجلسة،
وحُسبت sha256 بشكل مستقل. **كل التجزئات طابقت القيم المعلنة في المقترح** (بمقارنة البادئة الثمانية).

| المصدر (المستودع @ SHA) | الملف | sha256 (مستقل) | الأسطر | مطابقة ادّعاء المقترح |
| --- | --- | --- | --- | --- |
| `OpenHands/enterprise@3fac53df…` | `app_conversation/additional_repositories.py` | `a8d0bbe3…` | 453 | ✅ |
| `enterprise@3fac53df…` | `app_conversation/app_conversation_router.py` | `c43ed4f7…` | 2209 | ✅ |
| `enterprise@3fac53df…` | `sandbox/lifecycle/tasks.py` | `834e9452…` | 190 | ✅ |
| `enterprise@3fac53df…` | `sandbox/lifecycle/sweep.py` | `1d99bd1c…` | 57 | ✅ |
| `enterprise@3fac53df…` | `sandbox/lifecycle/settings.py` | `1cdd88d5…` | 31 | (غير مُدرج بالتفصيل) |
| `enterprise@3fac53df…` | `sandbox/lifecycle/rules.py` | `0f0df7a9…` | 118 | (غير مُدرج بالتفصيل) |
| `enterprise@3fac53df…` | `sandbox/lifecycle/__init__.py` | `446effa0…` | 15 | ✅ (نصّ النطاق) |
| `enterprise@3fac53df…` | `worker/app.py` | `a287ec5a…` | 37 | ✅ |
| `enterprise@3fac53df…` | `app_conversation/app_conversation_models.py` | `7a4a54c0…` | 710 | ✅ |
| `enterprise@3fac53df…` | `app_conversation/live_status_app_conversation_service.py` | `9f4f1596…` | 4696 | ✅ |
| `enterprise@3fac53df…` | `sandbox/remote_sandbox_service.py` | `d239ec43…` | 1547 | ✅ |
| `enterprise@3fac53df…` | `sandbox/workspace_archive.py` | `202fc8e1…` | 543 | ✅ |
| `enterprise@3fac53df…` | `sandbox/docker_sandbox_service.py` | `00953ee1…` | 900 | ✅ (`container.remove()`) |
| `enterprise@3fac53df…` | `sandbox/docker_sandbox_spec_service.py` | `5401c0b7…` | 170 | ✅ (`/workspace/project`) |
| `enterprise@3fac53df…` | `sandbox/sandbox_router.py` | `bb9bbe23…` | 497 | ✅ |
| `enterprise@3fac53df…` | `settings/settings_models.py` | `27bae62a…` | 1251 | ✅ (L753) |
| `enterprise@3fac53df…` | `frontend/src/api/conversation-service/v1-conversation-service.api.ts` | `0a0b80c6…` | 563 | ✅ |
| `enterprise@3fac53df…` | `sandbox/k8s_agent_sandbox_service.py` | `f70eec10…` | 897 | (تحقّق بودّية حذف k8s) |
| `OpenHands/software-agent-sdk@9f7d5cb1…` | `openhands-tools/…/tools/file_editor/editor.py` | `a1d735d4…` | 879 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-agent-server/…/agent_server/conversation_service.py` | `9e9b3e63…` | 3132 | ✅ |
| `sdk@9f7d5cb1…` | `…/agent_server/runtime_router.py` | `5bea70f0…` | 107 | ✅ |
| `sdk@9f7d5cb1…` | `…/agent_server/file_router.py` | `13f0cae7…` | 1209 | ✅ |
| `sdk@9f7d5cb1…` | `…/agent_server/api.py` | `5de71d80…` | 980 | ✅ |
| `sdk@9f7d5cb1…` | `…/agent_server/models.py` | `57b3680c…` | 732 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-sdk/…/sdk/llm/message.py` | `1b9f0693…` | 609 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-sdk/…/sdk/tool/defaults.py` | `357f005b…` | 194 | ✅ |
| `sdk@9f7d5cb1…` | `…/agent_server/server_details_router.py` | `2878f452…` | 192 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-sdk/…/workspace/remote/remote_workspace_mixin.py` | `0e55f7ab…` | 458 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-sdk/…/sdk/tool/schema.py` | `76b4f42a…` | 479 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-tools/…/terminal/terminal/terminal_session.py` | `72504a4d…` | 784 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-tools/…/file_editor/utils/constants.py` | `a5b3f2bf…` | 9 | ✅ (`MAX_RESPONSE_LEN_CHAR=16000`) |
| `sdk@9f7d5cb1…` | `openhands-tools/…/file_editor/impl.py` | `35353ad3…` | 107 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-tools/…/terminal/definition.py` | `a978161b…` | 362 | ✅ |
| `sdk@9f7d5cb1…` | `openhands-tools/…/gemini/read_file/impl.py` | `2d5f81f2…` | 153 | ✅ |
| `sdk@9f7d5cb1…` | `tests/agent_server/test_runtime_router.py` | `98f931d8…` | 252 | ✅ |
| `sdk@9f7d5cb1…` | `tests/cross/test_default_tool_names.py` | `3b406311…` | 79 | ✅ |
| `sdk@9f7d5cb1…` | `…/agent_server/conversation_registry.py` | `4a479391…` | 96 | ✅ |
| `sdk@9f7d5cb1…` | `…/agent_server/dependencies.py` | `f5f51362…` | 134 | ✅ |
| `OpenHands/sandbox-server@43e91604…` | `app_conversation/app_conversation_router.py` | `864bff55…` | 1719 | ✅ |
| `sandbox-server@43e91604…` | `app_conversation/live_status_app_conversation_service.py` | `9653dd3d…` | 3162 | ✅ |
| `sandbox-server@43e91604…` | `sandbox/remote_sandbox_service.py` | `c523a807…` | 1150 | ✅ |
| `sandbox-server@43e91604…` | `sandbox/session_auth.py` | `893d725e…` | 139 | ✅ |
| `sandbox-server@43e91604…` | `sandbox/sandbox_router.py` | `07fef71e…` | 220 | ✅ (مكافئ R8-3) |
| `OpenHands/OpenHands@a8aaf681…` | `src/api/conversation-file-upload.api.ts` | `d5ae6b81…` | 197 | ✅ |
| `OpenHands@a8aaf681…` | `src/api/workspace-upload-path.ts` | `caabd831…` | 102 | ✅ |
| `OpenHands@a8aaf681…` | `src/api/agent-server-client-options.ts` | `78364c26…` | 82 | ✅ |
| `OpenHands@a8aaf681…` | `src/api/cloud/conversation-service.api.ts` | `94f38037…` | 381 | ✅ |
| `OpenHands@a8aaf681…` | `src/utils/file-validation.ts` | `51b16ff5…` | 70 | ✅ (3 MiB/3 MiB) |
| Cloud V1 حيّ | `https://app.all-hands.dev/openapi.json` | `f0f4d4e9…` | — | ✅ `1.91.0`, 244 paths |

**حدود الشفافية:** لم أُعد جلب بضعة ملفات هامشية في قائمة §11 (مثل `gemini/read_file/definition.py`,
`file_editor/definition.py`) لأنها غير محمّلة لأي ملاحظة أو ادّعاء جوهري؛ تُصنَّف **غير مُتحقَّق منها في هذه
الجلسة** (لا تُمنح PASS). كل المصادر الجوهرية للملاحظات N11 وكل محاور الانحدار جُلبت وحُقّقت.

---

## 4. الملاحظات الأساسية: N11-1 / N11-2 / N11-3

### N11-1 — `additional_repositories.py` (خط 89 مقابل خط 106)

**الأرضية (`enterprise@3fac53df…`, sha256 `a8d0bbe3…`, 453 سطرًا) — أُعيد اشتقاقها:**
- **L89:** `def conversation_repositories(` — **تعريف الدالة**.
- **L106:** `path=f'{working_dir}/{folder}' if working_dir else None,` — **تعبير بناء المسار** (داخل
  `ConversationRepository(...)` في فرع `selected_repository`).
- ملاحظة: يوجد تعبير `path=f'{working_dir}/{folder}'` **ثانٍ** عند **L155**، لكنه داخل دالة **مختلفة**
  (`def conversation_roots(` عند L138) — انظر N12-2.

**ما يفعله r12:** يذكر الآن **الرمز + نطاق الأسطر المتحقَّق منه** في المواضع الثلاثة كلها:
- §1 (إشعار r9/R8-2): L336-337 — «`conversation_repositories` def at line 89; the
  `path=f'{working_dir}/{folder}'` expression at line 106».
- §5.15.6: L2109-2110 — نفس الصياغة.
- §11: L2918-2919 — نفس الصياغة.

**التحقّق:** لا يبقى أي نسبة خاطئة للتعبير إلى L89 خارج إشعار التصحيح (حيث تُقتبس الصياغة المسحوبة
للتوضيح فقط). النثر المحيط يصف ما يُثبته المصدر (قراءة المسار من الوسم) **ولا يوحي** بضمانات أقوى
(الربط/التفويض مصنَّف صراحةً **NEW/UNVERIFIED** في §5.15.6 وQ22).

**الحُكم: `VERIFIED` — مُعالَج بالكامل.**

### N11-2 — `app_conversation_router.py` (خط 1185 مقابل خط 1188)

**الأرضية (`enterprise@3fac53df…`, sha256 `c43ed4f7…`, 2209 سطرًا) — أُعيد اشتقاقها:**
- **L1185:** `# Delete the sandbox in the background if no other conversations reference it` — **تعليق**.
- **L1188:** `workspace_path = app_conversation_info.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)` — **القراءة**.
- **L1189:** `asyncio.create_task(` — صحيح كما ذُكر سابقًا.
- **L1085-1091:** كتلة `conversation_count = (await … count_conversations_by_sandbox_id(…))` + `if
  conversation_count == 0: await sandbox_service.delete_sandbox(sandbox_id)` (L1085 بداية الكتلة، L1083 نهاية
  تحذير الفشل).

**ما يفعله r12:** §11 (L2882-2884) يذكر الآن: `count_conversations_by_sandbox_id(...) == 0` **(lines
1085-1091)**؛ `asyncio.create_task` **(line 1189)**؛ و`workspace_path` = الوسم **(line 1188: …; line 1185
هو التعليق السابق)**.

**التحقّق:** دقيق. لا يُخلَط حذف الـ sandbox/container مع الحذف الفيزيائي لبيانات مساحة العمل (§5.10.4
يفصل صراحةً بين إزالة الحاوية والحذف الفيزيائي)، ولا يُستنتَج سلوك دورة حياة Cloud/runtime-api دون دليل
(مصنَّف «مُفوَّض إلى runtime-api» / خارجي).

**الحُكم: `VERIFIED` — مُعالَج بالكامل.**

### N11-3 — إسناد cron: `sweep.py` مقابل `tasks.py`

**الأرضية (`enterprise@3fac53df…`) — أُعيد اشتقاقها:**
- `sandbox/lifecycle/tasks.py` (sha256 `834e9452…`, 190 سطرًا): **L78**
  `@lifecycle.periodic(cron='* * * * *')`؛ **L79-81** `@lifecycle.task(name='sweep', …)`؛ **L82**
  `async def sweep(context, timestamp)`؛ **L113** `@lifecycle.task(name='check')`؛ **L182**
  `await sandbox_service.delete_sandbox(sandbox_id)` داخل `elif decision.action == Action.DELETE`.
- `sandbox/lifecycle/sweep.py` (sha256 `1d99bd1c…`, 57 سطرًا): **لا يوجد أي token لـ `cron`**؛ يحوي
  `LAST_RAN_AT = func.greatest(...)` (L20) و`find_due_sandbox_ids` (L42).
- `sandbox/lifecycle/rules.py` (sha256 `0f0df7a9…`): `decide()` (L74) → `Action.DELETE`/`Reason.INACTIVE` (L108).
- `sandbox/lifecycle/__init__.py` (sha256 `446effa0…`): النطاق «covers every backend that subclasses
  `ManagedSandboxServiceInjector`: Docker, E2B and k8s agent-sandbox. runtime-api manages the remote
  backend's sandboxes itself» + «`sandbox_lifecycle:sweep` runs every minute … from the sandbox table alone».

**ما يفعله r12:** §5.10.4 (L1459-1460) و§11 (L2933-2935) ينسبان الآن **إعلان المهمة المجدولة** إلى
**`tasks.py`** (L78؛ `name='sweep'` L80) و**اختيار المرشّحين** إلى `sweep.py`
(`find_due_sandbox_ids`)، مع سلسلة السلوك `rules.py::decide` → `Action.DELETE` → `tasks.py` →
`sandbox_service.delete_sandbox(...)`.

**التحقّق:** دقيق، ويحفظ التمييز الصريح بين: (1) إعلان المهمة المجدولة، (2) تنفيذ الـ sweep واختيار
المعرّفات المستحقة، (3) قرار القاعدة، (4) استدعاء الحذف، (5) الحذف الفيزيائي الفعلي **الذي لا يُستنتَج
دون دليل** (نصّ r12: «does not imply that the cron declaration proves successful execution or physical
workspace deletion»). لا ادّعاء بأن إعلان cron دليل على نجاح تشغيل أو حذف فيزيائي.

**الحُكم: `VERIFIED` — مُعالَج بالكامل.**

---

## 5. مراجعة الانحدار الكامل (N10, R9, R8, R7, R6, N-1…N-5)

أُعيد فتح المقترح كاملًا وتحقّقت كل ملاحظة سابقة من المصدر المثبّت (لا من التقرير).

| الملاحظة | موضع المعالجة في r12 | تحقّق المصدر المستقل | الحُكم |
| --- | --- | --- | --- |
| **N10-1** (`editor.py` حرس المسار المفقود) | §5.15.5 L2060-2062؛ §11 L2819-2822 | `editor.py` `a1d735d4…`: `def validate_path` L657؛ `if not is_host_absolute_path(path)` L666؛ `if command != "create" and not path.exists():` L689؛ `raise EditorToolParameterInvalidError(` L690 (النطاق 689-694) | ✅ مُعالَج ومتّسق في الموضعين |
| **N10-2** (`conversation_service.py` تحت SDK لا enterprise) | §11 L2826-2832 وL2890-2892 | الملف في `software-agent-sdk@9f7d5cb1…` (`9e9b3e63…`, 3132 سطرًا؛ `delete_conversation` L1863؛ تعليق «workspace is preserved» L1911). استعلام GitHub لـ `OpenHands/enterprise` على مسار `conversation_service.py` ⇒ **404** | ✅ مُعالَج |
| **N10-3** (وضع `1.87.1` التاريخي) | §1 L353؛ §2.1 L603؛ §2.2 L621/626/694؛ §11 L2756-2762 | القيمة الحالية الحيّة: `1.91.0`, 244 paths, `f0f4d4e9…` (أُعيد جلبها)؛ القيمة التاريخية `1.87.1`/242 موسومة **NOT INDEPENDENTLY VERIFIED** في كل موضع (7 مواضع) | ✅ مُعالَج |
| **R9-1** (مؤقّت العملية مقابل مؤقّت البنية التحتية) | §1 L370-374؛ §5.10.4 L1509-1513؛ T-24؛ Q18 L3119-3137 | `settings.py` `delete_after_seconds` (افتراضي 10 أيام) منفصل عن `expires_at`؛ `rules.py` L108 `Action.DELETE` | ✅ متّسق |
| **R9-2** (`RESERVED_TAG_KEYS` سطر 86) | §11 L2909-2911 | `app_conversation_models.py` `7a4a54c0…`: `RESERVED_TAG_KEYS = frozenset(` **L86**؛ `def _validate_caller_tags(` **L96** | ✅ مُعالَج (التصحيح من «96» إلى «86») |
| **R9-3** (إزالة الحاوية مقابل الحذف الفيزيائي) | §5.10.4 L1471-1489؛ §11 L2893-2901 | `docker_sandbox_service.py` `_delete_at_provider` L686 → `container.remove()` L698؛ `mounts: list[VolumeMount] = Field(default_factory=list)` (افتراضي فارغ) L741؛ k8s `k8s_agent_sandbox_service.py` `_delete_at_provider` L792 | ✅ مُعالَج |
| **R9-4** (تجزئة المواصفة التاريخية موسومة) | §11 L2756-2762 | لا يوجد أثر لـ r8 على القرص؛ القيمة التاريخية موسومة **NOT INDEPENDENTLY VERIFIED** | ✅ مُعالَج |
| **R8-1** (المسار الفيزيائي **مُنمذَج**) | §1 L325-330؛ §5.10.4 L1453-1525؛ Q18 | وجود `sandbox/lifecycle/{settings,rules,tasks,sweep}.py` + `worker/app.py` L33 `add_tasks_from(lifecycle, namespace='sandbox_lifecycle')` | ✅ مُعالَج |
| **R8-2** (قراءة الجذر موجودة؛ الربط جديد) | §1 L331-345؛ §5.14.2 step 3 L1732-1754؛ §5.15.6 L2101-2150؛ U-12؛ Q22 | `app_conversation_models.py` L250-265 `@computed_field repositories` تقرأ `tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)` L263؛ `runtime_router.py` L41-43؛ المواصفة الحيّة تُظهر `AppConversation.repositories` و`ConversationRepository.path` = «Absolute path of the folder in the sandbox» | ✅ مُعالَج |
| **R8-3** (عيب استشهاد: تجزئة `bb9bbe23…`) | §11 L2747؛ L2888 | `enterprise/sandbox/sandbox_router.py` = `bb9bbe23…` (497 سطرًا)؛ `sandbox-server/sandbox/sandbox_router.py` = `07fef71e…` (220 سطرًا) | ✅ مُعالَج |
| **R8-4** (مواصفة تاريخية r8) | §1 L353-357؛ §2.2؛ §11 | كما N10-3 | ✅ مُعالَج |
| **R7-1** (حذف المحادثة يؤرشف ولا يستعيد C2) | §5.10.4 L1495-1503؛ §11 L2885-2901 | `app_conversation_router.py` `_finalize_sandbox_delete` L1050؛ `archive_conversation_workspace` L1071؛ `remote_sandbox_service.py::delete_sandbox` L917 («Purely sandbox-scoped … never archives») | ✅ متّسق |
| **R7-2** (مصدر الجذر) | §5.14.2 step 3؛ §5.15.6 | `AgentServerContext` (L219-227) بلا حقل مسار مساحة عمل؛ `_get_agent_server_context` يعرض `sandbox_spec.working_dir` فقط | ✅ متّسق |
| **R7-3** (نسخة مُستنسخة/مُستطلع عليها) | §2.2 L669-675؛ §5.15.4؛ Q20 | `remote_sandbox_service.py` `poll_agent_servers` L1256 → `refresh_conversation` L1345 → `save_event` L1438؛ `if web_url is None or 'localhost' in web_url:` L1519 | ✅ متّسق |
| **R7-4** (خريطة L↔F) | §5.10.0.1 | تمييز `L6↔F6b`, `L7↔F7` فقط | ✅ متّسق |
| **R6-1** (نسخة مساحة العمل لا تُحذف عند `expires_at`) | §5.10.4 L1449-1452؛ T-24؛ I12؛ §9 7b | متّسق داخليًا عبر §5.9/§5.10.1/§5.10.2/§5.10.3/§5.14.2 step 7/§8.4 | ✅ متّسق |
| **R6-2** (حدّ ثقة المُصدِر U-3) | §5.15.1-§5.15.3؛ T-22؛ Q16/Q19 | لا يوجد مُصدِر موثوق في المصدر المثبّت — مصنَّف **UNVERIFIED** | ✅ متّسق |
| **R6-3** (اتساق الدليل) | §5.15.4؛ Q20 | كما R7-3 | ✅ متّسق |
| **R6-4** (المسار المطلق) | §5.15.5؛ U-11؛ Q21 | `editor.py` يرفض المسار النسبي (L666) | ✅ متّسق |
| **R6-5** (صياغة «seven lifecycle facts») | إشعار r7؛ §5.14.0 | المواضع الحيّة تستخدم «eight»؛ المواضع المتبقية من كلمة «seven» تاريخية/سياقية فقط | ✅ متّسق |
| **N-1** (قاعدة دليل القراءة الناجحة) | إشعار r6 L180-190؛ §5.14.0 L1643-1680 | `schema.py` `is_error` افتراضيًا `False` (L400/L417)؛ `terminal_session.py`: `is_error=True` فقط في الحالات التفاعلية/فارغ/أوامر متعدّدة/طرفية مغلقة (L506, L520, L526, L542, L670)، ومسار الأمر المكتمل (`_handle_completed_command` L241) يُعيد `TerminalObservation.from_text(...)` **دون** ضبط `is_error` | ✅ مُعالَج ومؤكَّد من المصدر |
| **N-2** (`accepted` → `stored` في المثال) | §5.5 L988-1027 | المثال يعرض `"state": "stored"` | ✅ مُعالَج |
| **N-3** (قبول `pending-messages` مُبالَغ فيه) | §2.2 L659-664؛ §5.9.1؛ §5.15 U-2؛ Q12/Q15 | `_process_pending_messages` يُستدعى من مسار البدء فقط (L1239 بعد `READY` L1226) | ✅ مُعالَج |
| **N-4** (قارئ `cat` بلا إشارة نجاح) | §5.14.2 step 5 | المصدر يؤكّد غياب إشارة نجاح | ✅ مُعالَج |
| **N-5** (هوية مراجعة قديمة) | الهيدر L3-14؛ §13 | الهيدر يعرّف r12؛ §13 يحوي صف r12 | ✅ مُعالَج (لكن انظر N12-1 للتنسيق) |

**محاور إضافية فُحصت:** غياب مسار رفع في Cloud V1 (0 مسارات upload/attach؛ 0 `multipart/form-data`؛ 0
`format: binary`؛ أنواع الطلب فقط `application/json` و`application/x-www-form-urlencoded` على مسارات
`/oauth/*` الخمسة)؛ `send-message` = `anyOf[TextContent, ImageContent]` بـ `minItems: 1`؛ غياب
`UploadFile`/`multipart` في `openhands/app_server` داخل enterprise (0 نتيجة)؛ `web_url is None or
'localhost'`؛ `container.remove()`؛ `RESERVED_TAG_KEYS` L86؛ دلالات النسخة المُستنسخة؛ حدود أصل/تفويض
الجذر؛ ادّعاءات محرّر الملفات/التنظيف/إكمال الأحداث/التنفيذ الطرفي/التسليم المتين — **كلها متّسقة ولم
تُضعَف**.

---

## 6. الفحص البنيوي والدلالي

- **أسوار الكود:** 6 (زوجية ومتوازنة) عند L971/976/988/1001/1111/1129.
- **I1–I15:** موجودة (15 صفًا، L2424-2438). **T-01…T-25:** 25 صفًا؛ T-19 (L2221)، T-24 (L2226)، T-25
  (L2227) موجودة ومُنطَّقة. **U-1…U-12:** 12 صفًا (بما فيها U-12 عند L1915). **C1–C5:** 5 (L1318-1322).
  **Q1–Q22:** 22 (بما فيها Q18 C2-retention وQ22 U-12).
- **§9:** البنود 1–11 بما فيها **7b** و**7c** موجودة (لم يُخفَّف أي معيار).
- **§13:** يحتوي **صف r12 واحدًا بالضبط** (L3185) — لكن انظر N12-1.
- **لا تحويل لقرارات المالك غير المحسومة إلى محسومة:** U-3/U-10/U-11/U-12 وQ18/Q22 وU-2 لا تزال مفتوحة
  صراحةً (§7).
- **لا ادّعاء بأن الـ API موجود:** §1/§2.2/§7.0/§8 تنصّ على أن القدرة **غير موجودة** وأن P0 **غير منفَّذ**.
- **لا إضعاف للأمان/الملكية/التفويض/الاحتفاظ/الانتهاء/التنظيف/معالجة الفشل:** القواعد fail-closed محفوظة؛
  لا بدائية تنظيف مُختَرَعة.

---

## 7. القرارات المفتوحة للمالك والاعتماديات الخارجية

تبقى **مفتوحة صراحةً** (لم تُحسم تلقائيًا):

1. **U-3 (حدّ المُصدِر الموثوق):** لا يوجد مُصدِر موثوق في المصدر المثبّت — **UNVERIFIED** (§5.15.1، Q16/Q19).
2. **U-10 (مصدر دليل مُهدَّأ):** النسخة المُستنسخة ليست لقطة متّسقة (§5.15.4، Q20).
3. **U-11 (عقد المسار المطلق):** مطلوب للضمان I14 (§5.15.5، Q21).
4. **U-12 (ربط/تفويض الجذر):** **NEW/UNVERIFIED** — القراءة موجودة، الربط جديد (§5.15.6، T-25، I15، Q22).
5. **C2 retention (Q18):** لا سياسة احتفاظ مقيَّدة؛ الافتراضي المحافظ (لا استعادة عبر حدث محادثة) قائم.
6. **دورة حياة/تفكيك Cloud/runtime-api:** **مُفوَّض إلى runtime-api** — خارجي/غير مُنمذَج في هذه المستودعات.
7. **القبول المتين للمحادثة النشطة (U-2):** جديد (مسار `pending-messages` للبدء فقط).
8. **قرار المنتج:** هل يُنفَّذ P0 أصلًا أم يبقى الرفض fail-closed (Q11) — **قرار المالك، غير محسوم هنا**.

لا يختار المقترح قرار مالك بصمت، ولا يعرض قدرة غير متحقَّقة كمتاحة.

---

## 8. مصفوفة الادّعاء ↔ المصدر (الادّعاءات الجوهرية)

| §/السطر | الادّعاء | المستودع @ SHA | الملف/الأسطر | استرجاع مستقل | تطابق التجزئة | الحُكم |
| --- | --- | --- | --- | --- | --- | --- |
| §5.15.6 L2109 / §11 L2918 | `conversation_repositories` تبني `path={working_dir}/{folder}` (def L89؛ expr L106) | enterprise@3fac53df | `additional_repositories.py` L89/L106 | نعم | نعم `a8d0bbe3` | **VERIFIED** |
| §11 L2882-2884 | قراءة وسم `archiveworkspacepath` عند L1188؛ create_task L1189؛ كتلة العدّ L1085-1091 | enterprise@3fac53df | `app_conversation_router.py` L1085-1091, L1188-1189 | نعم | نعم `c43ed4f7` | **VERIFIED** |
| §5.10.4 L1459 / §11 L2933 | cron `* * * * *` في `tasks.py` L78؛ `sweep.py` بلا cron | enterprise@3fac53df | `tasks.py` L78/L80/L82؛ `sweep.py` | نعم | نعم `834e9452`/`1d99bd1c` | **VERIFIED** |
| §11 L2819-2822 | حرس المسار المفقود `editor.py` L689/L690 | sdk@9f7d5cb1 | `file_editor/editor.py` L657/L666/L689/L690 | نعم | نعم `a1d735d4` | **VERIFIED** |
| §11 L2826-2832 | `conversation_service.py` في SDK لا enterprise | sdk@9f7d5cb1 / enterprise | `conversation_service.py` L1863/L1911 | نعم | نعم `9e9b3e63`؛ enterprise 404 | **VERIFIED** |
| §2.2 L621/626/694 | لا مسار رفع في Cloud V1 | Cloud V1 حيّ | `openapi.json` 1.91.0/244 | نعم | نعم `f0f4d4e9` | **VERIFIED** |
| §2.2 L636-637 | `send-message` = anyOf[Text,Image] | Cloud V1 حيّ | `AppSendMessageRequest` | نعم | نعم | **VERIFIED** |
| §5.15.6 L2115 | `RESERVED_TAG_KEYS` L86 | enterprise@3fac53df | `app_conversation_models.py` L86/L96 | نعم | نعم `7a4a54c0` | **VERIFIED** |
| §5.10.4 L1472-1483 | `container.remove()`؛ mounts افتراضية فارغة | enterprise@3fac53df | `docker_sandbox_service.py` L698/L741 | نعم | نعم `00953ee1` | **VERIFIED** |
| §5.15.4 / §2.2 L669-671 | poll فقط بلا URL عام | enterprise@3fac53df | `remote_sandbox_service.py` L1256/L1438/L1519 | نعم | نعم `d239ec43` | **VERIFIED** |
| §5.15.5 L2060 | حرس `is_host_absolute_path` L666 | sdk@9f7d5cb1 | `editor.py` L666 | نعم | نعم `a1d735d4` | **VERIFIED** |
| §5.14.0 L1647-1655 | `is_error` افتراضيًا False؛ الطرفية لا تضبطه للأمر المكتمل | sdk@9f7d5cb1 | `schema.py` L400/L417؛ `terminal_session.py` L241/L506/L670 | نعم | نعم `76b4f42a`/`72504a4d` | **VERIFIED** |
| §11 L2916-2921 | `AppConversation.repositories` حيّ | Cloud V1 حيّ | `AppConversation`/`ConversationRepository.path` | نعم | نعم | **VERIFIED** |
| §5.14.2 step 3 L1742 | `bind_local_conversation_runtime` يشتق الجذر | sdk@9f7d5cb1 | `runtime_router.py` L41-43/L47-48 | نعم | نعم `5bea70f0` | **VERIFIED** |

**حدود:** ادّعاءات §11 الهامشية غير المحمّلة لأي ملاحظة تُصنَّف **UNVERIFIED في هذه الجلسة** (لم تُجلب)،
ولا تُمنح PASS.

---

## 9. الملاحظات مرتّبة حسب الشدّة (مع المواضع الدقيقة)

**N12-1 — LOW (توثيقي/Markdown؛ غير حاجز).** جدول سجل المراجعات في §13 مقطوع بسطر فارغ عند **L3184**:
الصف r11 في L3183، ثم سطر فارغ L3184، ثم الصف r12 في L3185. في Markdown (GFM) يُنهي السطر الفارغ
الجدول، فيُعرض صف r12 **كجدول منفصل من صف واحد** بدل أن يكون جزءًا من سجل المراجعات. هذا هو **القطع
الداخلي الوحيد** في الجدول في الوثيقة كلها (كل الجداول الأخرى متّصلة). **السبب:** إضافة صف r12 أُدرجت
بسطر فارغ سابق. **التأثير:** تنسيقي بحت — لا يغيّر أي ادّعاء تقني ولا أي شرط أمني؛ صف r12 موجود
**مرة واحدة** ومحتواه صحيح. **الإصلاح المقترح (غير حاجز):** إزالة السطر الفارغ L3184 لتلتحم صفوف §13.

**N12-2 — INFO (توضيحي؛ ليس عيبًا).** تصحيح N11-1 يستشهد بـ «line 106» لتعبير
`path=f'{working_dir}/{folder}'`؛ يوجد تعبير **ثانٍ** بالشكل نفسه عند L155 داخل
`conversation_roots` (دالة مختلفة، L138). لأن المقترح يسمّي الدالة **مع** السطر، فالمرجع **غير ملتبس**؛
لا يلزم إجراء.

**N12-3 — INFO (شفافية).** يُلاحَظ أن r12 غيّر أيضًا استشهادًا مجاورًا في جملة N11-2 من «lines
1083-1091» إلى «lines 1085-1091»؛ هذا تصحيح دقّة صحيح (L1085 بداية الكتلة، L1083 نهاية تحذير الفشل)
ولا يغيّر أي ادّعاء.

**ملاحظة منهجية:** لم أجد أي استشهاد سطر قديم متبقٍّ، ولا سطرًا صحيحًا مرتبطًا برمز خاطئ، ولا ملفًا
منسوبًا لمستودع خاطئ، ولا تجزئة تاريخية مُقدَّمة كدليل حالي، ولا ادّعاءً أوسع من المصدر، ولا تضاربًا بين
الأقسام، ولا افتراضًا خفيًّا عن بنية تحتية مُستضافة، ولا متطلّبًا غير قابل للإنفاذ التشغيلي، ولا تعديلًا
r12 أضعف ثابتًا أمنيًا سابقًا.

---

## 10. التمييز الصريح: مراجعة المقترح مقابل جاهزية التنفيذ

- **حُكم مراجعة المقترح:** `PASS_WITH_NOTES` (الملاحظات الثلاث N11 مُعالَجة بالكامل ومُتحقَّق منها؛ ملاحظة
  تنسيقية واحدة غير حاجزة N12-1).
- **جاهزية التنفيذ: ليست جاهزة.** المقترح **ليس تنفيذًا**؛ **لا** يوجد نقطة رفع آمنة، **لا** ادّعاء بوجود
  قدرة رفع آمنة، **لا** تفويض تنفيذ ضمني، و**P0 يبقى مفتوحًا وغير مُنفَّذ وغير مُعتمَد**.
- **قرارات المالك المطلوبة:** U-3/U-10/U-11/U-12-binding، سياسة احتفاظ C2 (Q18)، حدّ تفكيك
  Cloud/runtime-api، القبول المتين U-2، وقرار تنفيذ المنتج (Q11).

---

## 11. مقارنة الشجرة الابتدائية/النهائية

- **الابتدائية:** كما في §2 (4 ملفات `M`، و23 ملفًا `??`).
- **النهائية:** نفس الحالة **بالإضافة إلى** ملف واحد جديد غير متعقَّب:
  `?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- **الفرق الوحيد:** إنشاء ملف المراجعة هذا. لم يُعدَّل أي ملف قائم (بما فيه المقترح والمراجعة الذاتية
  R12 و`PROGRESS.md` والذاكرة).

---

## 12. تجزئات الملفات المحمية (الذاكرة/التقدّم) — قبل/بعد

| الملف | sha256 قبل | sha256 بعد | ثبات بايت-ببايت |
| --- | --- | --- | --- |
| `.openhands/memory/2026-11-11.md` | `a491ac02052a7ad217b4a70d7ace0883f2faa141d5de6baf79c3a64e1adc38ee` | نفسها | ✅ |
| `.openhands/memory/MEMORY.md` | `d89d56f481fca2c1b6698c117cccef162d8f94c0a1641f52fcf5906b75e56f82` | نفسها | ✅ |
| `.agent/PROGRESS.md` | `241d96954baffadf0c2281cf2933c5b6e4fe3dd5dff1d06a3e08d15348002779` | نفسها | ✅ |

---

## 13. قائمة الملفات المُنشأة/المُعدَّلة بدقّة

- **مُنشأ (1 فقط):** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- **مُعدَّل:** **لا شيء**.

---

## 14. تأكيد العمليات المحظورة التي لم تُنفَّذ

**لم يُنفَّذ:** أي تعديل على المقترح أو أي مراجعة قائمة أو `PROGRESS.md` أو أي ملف ذاكرة أو الكود أو
الاختبارات أو المخططات أو الترحيلات أو الإعدادات أو أي توثيق غير ذي صلة؛ لا `git reset`/`git clean`/
`checkout`/`restore`/`stash`/حذف واسع؛ لا `git add .`/`git add -A`؛ لا commit/push/PR/merge/إنشاء أو
تبديل فرع/نشر؛ لا استدعاء API إنتاجي؛ لا استخدام أسرار أو اعتمادات أو بيانات مستخدمين حيّة؛ لا تواصل مع
المشرفين. الملف الوحيد المُنشأ هو هذا. **لم تحدث أي مخالفة نطاق.**

---

## 15. التوصية للخطوة التالية (واحدة)

دمج التصحيح التوثيقي غير الحاجز **N12-1** (إزالة السطر الفارغ عند §13 L3184 لالتحام جدول سجل
المراجعات)، ثم الانتقال إلى `PASS` على محور الاستشهاد — مع إبقاء P0 **غير مُنفَّذ وغير مُعتمَد** إلى أن
يُحسم **U-12** (ربط/تفويض الجذر) و**U-3** (المُصدِر الموثوق) وسياسة احتفاظ **C2 (Q18)**.

---

**إفصاح الاستقلالية.** أُعِدَّت هذه المراجعة بواسطة مراجِع بسياق جديد ليس مؤلّف مقترح r12، ولا المراجعة
الذاتية R12، ولا أي مراجعة/مراجعة ذاتية سابقة في هذه السلسلة. جميع الأعمال كانت قراءة فقط؛ الملف الوحيد
المُنشأ هو هذا. لم تُستخدم أي أسرار أو اعتمادات أو استدعاءات إنتاجية.

*أُعِدَّت هذه المراجعة بواسطة وكيل ذكاء اصطناعي (OpenHands) نيابةً عن مالك المستودع.*
