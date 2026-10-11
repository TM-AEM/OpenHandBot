# ملاحظات OpenHands Cloud API — نتائج المرحلة 0

اتأكدت عمليًا في 2026-10-11 من `https://app.all-hands.dev/api/v1`.

## المصادقة
- الثلاثة headers شغالة: `Authorization: Bearer`، `X-Access-Token`، `X-Session-API-Key`.
- البوت يستخدم `Authorization: Bearer` (الأوضح في دليل Cloud API).

## قايمة الشاتات
`GET /app-conversations/search?limit=N`
- ترجّع `{"items": [...], "next_page_id": ...}` (object مش array).
- الترتيب الافتراضي تقريبًا `updated_at` تنازلي. الخطة تقول الترتيب مش موثق، فالبوت بيرتّب client-side بـ `updated_at` كضمان.
- `execution_status` بيرجع `null` لبعض الشاتات القديمة (PAUSED) — لازم التعامل مع None.
- `next_page_id` ممكن يكون `null`.
- الحقول المهمة لكل عنصر: `id`، `title`، `selected_repository`، `selected_branch`، `sandbox_id`، `sandbox_status`، `execution_status`، `updated_at`، `conversation_ui_url`.

## حالة شات أو أكتر
`GET /app-conversations?ids=ID1&ids=ID2` — معرّفات متكررة في نفس الباراميتر.
- ترجّع **array**، وعناصرها ممكن تكون `null` (اتأكدنا).
- الفاصلة `,` بين المعرّفات ترجّع 400 (`Invalid UUID format`).

## آخر رد
`GET /conversation/{id}/events/search?sort_order=TIMESTAMP_DESC&limit=50`
- ترجّع `{"items": [...]}`. الحد الأقصى لـ `limit` = **100** (200 ترجّع 422).
- `kind__eq` يقبل القيم دي بس: `ServerErrorEvent, ACPToolCallEvent, Condensation, CondensationRequest, CondensationSummaryEvent, ConversationErrorEvent, ConversationStateUpdateEvent, HookExecutionEvent, LLMCompletionLogEvent, ActionEvent, MessageEvent, AgentErrorEvent, ObservationEvent, UserRejectObservation, SystemPromptEvent, StreamingDeltaEvent, TokenEvent, InterruptEvent, PauseEvent`.
- **`FinishAction` مش قيمة صحيحة لـ `kind__eq`** (422) — لأنه نوع `ActionEvent`. لازم تجيب `ActionEvent` وتفلتر بنفسك على `action.kind == "FinishAction"`.
- رد الـ agent العادي: `MessageEvent` بحيث `source == "agent"` والنص في **`llm_message.content[].text`** (مش في `event.message`).
- في مراقبة دي كانت آخر `MessageEvent` من الـ agent، مفيش `FinishAction` ظهر.

## إرسال برومت
`POST /app-conversations/{id}/send-message`
جسم: `{"role":"user","content":[{"type":"text","text":...}],"run":true}`
- على sandbox **PAUSED** → **409** و`detail` بيقول:
  `Sandbox is PAUSED. Use POST /api/v1/sandboxes/{sandbox_id}/resume to resume it first.`
- `sandbox_id` موجود كحقل على عنصر الشات.

## شات جديد
`POST /app-conversations` جسم: `{"initial_message":{"content":[{"type":"text","text":...}]}, "selected_repository":...}`
- بيرجّع start task فيه `id`.
- `GET /app-conversations/start-tasks?ids=TASK_ID` → **array عناصرها ممكن `null`**. استنى `status == "READY"` وخد `app_conversation_id`. (المسار ده ماتمرنش live على شات جديد في المرحلة 0، اتأكد شكله فقط.)
- `selected_repository` اختياري حسب الخطة؛ البوت بيدعم بدونه.

## المستودعات
`GET /git/repositories/search?provider=github&limit=100`
- ترجّع `{"items":[...]}`، كل عنصر فيه `full_name`، `main_branch`، `is_public`.
- 16 مستودع لـ `TM-AEM`.

## مرجع
- https://docs.openhands.dev/openhands/usage/cloud/cloud-api.md
