# OHB2 — Poller Concurrency Option A Independent Review Handoff

**Task ID:** `OHB2-POLLER-CONCURRENCY-OPTION-A-IMPLEMENTATION-REVISED`
**Status:** implementation complete; independent review not yet performed
**Base commit:** `0774c9cff923a2ed02da36a1111a283a61600ea5`
**Base tree:** `faa7a3f03aa361698c6854281c162358bf38b84f`

## 1. Independence requirement

This handoff is for a **genuinely separate reviewer session** using a fresh clone or workspace. Do not
reuse the implementation conversation, its shell, or its working directory. A fresh clone created inside
the implementation conversation does not establish independent review.

The reviewer must report findings only and must not modify the implementation.

## 2. Candidate identity

There is **no candidate commit**. The candidate is an **unpublished working-tree diff** on `main` at the
base commit above. The authoritative candidate is the patch embedded in section 9.

| Item | Value |
|---|---|
| Candidate commit | none |
| Candidate state | unpublished working-tree diff |
| Changed files | `bot/app.py`, `tests/test_u04_concurrency.py` |
| Candidate patch size | 7,901 bytes |
| Candidate patch lines | 168 |
| Candidate patch SHA-256 | `a0eb63611a5ab738f442492b50a7db7c926f93a8a8deaa1e1110ef6be7573a84` |

Changed-file SHA-256 after the implementation:

| File | SHA-256 |
|---|---|
| `bot/app.py` | `aa7ebca7ae9e73c6f2452073f4a98da72dd557528a39135dd129a005dcc1b553` |
| `tests/test_u04_concurrency.py` | `4a0b5d83a10aaf65f65eebd210aa2c6e11dcb5460b6a785c1039f96a6158fae6` |

## 3. Reconstruction instructions

In a fresh clone:

```sh
git clone https://github.com/TM-AEM/OpenHandBot.git review-repo
cd review-repo
git checkout --detach 0774c9cff923a2ed02da36a1111a283a61600ea5
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Expected HEAD is `0774c9cff923a2ed02da36a1111a283a61600ea5` and tree is
`faa7a3f03aa361698c6854281c162358bf38b84f`.

Save the patch from section 9 as `candidate.patch`, then:

```sh
git apply --check candidate.patch
git apply candidate.patch
git status --short
sha256sum bot/app.py tests/test_u04_concurrency.py
```

Expected status is exactly:

```text
 M bot/app.py
 M tests/test_u04_concurrency.py
```

## 4. Preserved reports and audit integrity disclosure

The recovered audit report is:

`docs/audits/OHB2-POLLER-CONCURRENCY-STRUCTURAL-SAFETY-AUDIT-REPORT.md`

| Item | Value |
|---|---|
| Lines | 427 |
| Bytes | 27,936 |
| Actual SHA-256 | `f239dd86d97a63f7725ffbbf4cce7c7d6fc2775ff8c9727f0d967029b3824a9d` |
| Historical full hash | `1220fc23ea554eb9ce1a8a1842eb57617dc426f701ddc635308f1602fb509ef6` |
| Partial hash referenced in report | `d21de995ba04222dae910b27f50527258bad02f8203ff4d31c227e268b3365de` |
| Partial-hash length claim | first 28,836 bytes |

The recovered file is **not** byte-identical to the historical references. It is 27,936 bytes, while the
partial-hash description refers to 28,836 bytes. Neither historical hash matches the recovered file. The
owner explicitly authorized proceeding on the recovered report and the recorded audit findings; the
discrepancy must remain disclosed and the recovered report must not be edited.

The implementation report is:

`docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-IMPLEMENTATION-REPORT.md`

- Historical `BLOCKED` content was preserved; its pre-append SHA-256 was
  `7a0845cdcd92ccdc293bf34ca9b20a6503269825747174c493fe750e411afbbc`.
- The revised full report SHA-256 is
  `39e19cf3985a624b20a50770bda51d058ad1f83c282b37802d82324ca8bfbd89`.
- The report contains a clearly separated `Revised Attempt` section; the historical `BLOCKED` result was
  not erased.

## 5. What the implementation does

`bot/app.py` changes the PTB application builder from:

```python
.concurrent_updates(True)
```

to:

```python
.concurrent_updates(False)
```

With PTB 22.8, this yields `Application.concurrent_updates == 1` and
`Application._update_processor.max_concurrent_updates == 1`. It enforces sequential processing for updates
that pass through `Application.update_queue`.

The tests:

- `test_application_requires_sequential_updates` asserts the exact value `1` on the real application
  builder result.
- `test_queue_producers_are_serialized` uses two concurrent `update_queue.put()` producers and a real
  started `Application`; it verifies no overlap, `max in-flight == 1`, ordered start/end events, and
  completed queue accounting.
- `test_queue_continues_after_handler_exception` verifies a handler exception is handled, the next queued
  update still runs, and queue accounting completes.

The direct `Application.process_update()` limitation is documented: direct concurrent calls bypass the
queue/update-processor guarantee. No lock, wrapper, dispatcher, or Option B generation protection was
added.

## 6. Required independent checks

Use the project’s declared dependencies:

```sh
python -m venv /tmp/ohb2-review-venv
/tmp/ohb2-review-venv/bin/pip install -r requirements-dev.txt
```

Record the actual Python, PTB, and pytest versions.

Run at least:

```sh
/tmp/ohb2-review-venv/bin/python -m pytest -q tests/test_u04_concurrency.py
/tmp/ohb2-review-venv/bin/python -m pytest -q   tests/test_stage2_custom_polling.py   tests/test_duplicate_update_dispatch.py   tests/test_wp04_transient_classification.py   tests/test_file_browser.py   tests/test_bot_file_browser.py   tests/test_repair_plan_02_life01_f2_race.py
/tmp/ohb2-review-venv/bin/python -m pytest -q
/tmp/ohb2-review-venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/
/tmp/ohb2-review-venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
/tmp/ohb2-review-venv/bin/python -m pip_audit -r requirements-dev.txt
node --test tests/frontend/*.test.js
git diff --check
```

Also run a mutation check in an isolated copy: change `concurrent_updates(False)` to `True` and confirm
the configuration and queue tests fail. Do not modify the candidate workspace for the mutation check.

## 7. Protected-scope checklist

Confirm the candidate changes only these tracked paths:

- `bot/app.py`
- `tests/test_u04_concurrency.py`

Confirm there are no changes to:

- `bot/web/` or Mini App files
- `BrowserCache`, `browse_open`, `browse_refresh`, or REV-01 snapshot logic
- file-browser lifecycle or deletion behavior
- `_attachment_service` or DEF-011-A
- F-03/T-5 protected work
- outbox or workers
- Telegram polling architecture beyond the builder setting
- the recovered audit report
- the historical `BLOCKED` implementation-report content

The recovered audit report and implementation report are untracked in the implementation workspace and
must be preserved. No file should be staged or committed by the reviewer.

## 8. Review output

Report:

1. Whether the patch applies cleanly to the exact base.
2. Whether the changed files match the hashes above.
3. Whether Option A only was implemented.
4. Actual test/check commands, exit codes, and counts.
5. Whether the tests genuinely fail under `concurrent_updates(True)`.
6. Whether both reports were preserved and the audit-hash discrepancy disclosed.
7. Whether protected paths remained untouched.
8. Any findings, limitations, or residual risks.

Do not describe this review as independent unless it is actually performed in a separate reviewer
session.

## 9. Candidate patch

```diff
diff --git a/bot/app.py b/bot/app.py
index 67d2fa0..0060778 100644
--- a/bot/app.py
+++ b/bot/app.py
@@ -72,13 +72,14 @@ async def _register_commands(application: Application, owner_id: int) -> None:
 
 
 def build_application(config: Config) -> Application:
-    # OHB2-WP-07 (DEF-006): `concurrent_updates(True)` إعداد على `Application` بس — **مش**
-    # دليل إن الحلقة المخصّصة بتوزّع الدفعة بالتوازي. حلقة `bot.polling::TelegramPoller`
-    # بتوزّع التحديثات **تسلسليًّا** (`dispatch_and_wait`: تحطّ التحديث في الطابور وتستنّى
-    # `update_queue.join()` قبل اللي بعده) ⇒ تحديث بطيء/غير محسوم بيأخّر اللي بعده في الدفعة.
-    # الحكم على الإقرار **من البادئة المؤهّلة/النتيجة الدائمة**، مش من الإعداد ده.
-    # التزامن داخل الدفعة (`OD-04`) **ممنوع** بلا إثبات أمان على `Database._conn` وترتيب
-    # المستخدم؛ سياسة الاستطلاع المتسلسل مطابقة لـ `docs/OPERATIONS_RUNBOOK.md`.
+    # OHB2-WP-07 (DEF-006): `concurrent_updates(False)` يفرض معالجة تحديثات
+    # `update_queue` تسلسليًّا على مستوى `Application`، بدل الاعتماد فقط على أن حلقة
+    # `bot.polling::TelegramPoller` (`dispatch_and_wait`: تحطّ التحديث في الطابور وتستنّى
+    # `update_queue.join()` قبل اللي بعده) هي المنتج الوحيد. التزامن داخل الدفعة
+    # (`OD-04`) **ممنوع** بلا إثبات أمان على `Database._conn` وترتيب المستخدم؛ سياسة
+    # الاستطلاع المتسلسل مطابقة لـ `docs/OPERATIONS_RUNBOOK.md`.
+    # ملاحظة: هذا لا يسلسل النداءات المباشرة إلى `Application.process_update()` خارج
+    # `update_queue`، ولا العمليات الخلفية المنفصلة.
     # OHB2-STAGE2 (D0): نبني التطبيق **بدون Updater** (`updater(None)`) ⇒ PTB بيسييب
     # `update_queue` + `_update_fetcher` (بيوزّع على نفس الـ handlers) **بس مفيش سحب تلقائي**
     # ⇒ مفيش poller تاني؛ حلقة `bot.polling` المخصّصة هي اللي بتسحب (نفس العملية/القاعدة).
@@ -86,7 +87,7 @@ def build_application(config: Config) -> Application:
         Application.builder()
         .token(config.telegram_bot_token)
         .updater(None)
-        .concurrent_updates(True)
+        .concurrent_updates(False)
         .build()
     )
     client = OpenHandsClient(config.openhands_base_url, config.openhands_api_key)
diff --git a/tests/test_u04_concurrency.py b/tests/test_u04_concurrency.py
index 6555d07..98339da 100644
--- a/tests/test_u04_concurrency.py
+++ b/tests/test_u04_concurrency.py
@@ -1,7 +1,11 @@
-"""U04: استهلاك حالة التوجيه مرة واحدة، تأكيد الحفظ سريع، والتزامن مفعّل."""
+"""U04: استهلاك حالة التوجيه مرة واحدة، تأكيد الحفظ سريع، والتزامن التسلسلي."""
 import asyncio
 import time
 
+import pytest
+from telegram import Update
+from telegram.ext import TypeHandler
+
 import bot.handlers as h
 from bot.app import build_application
 from bot.config import Config
@@ -9,6 +13,7 @@ from bot.db import Database
 from bot import outbox
 
 from tests.test_handlers import make_context, make_update
+from tests.test_stage2_custom_polling import _with_started_app
 
 
 def test_take_awaiting_consumes_once(tmp_path):
@@ -95,7 +100,7 @@ def test_ack_means_durably_saved(tmp_path):
     assert seen["count"] == 1
 
 
-def test_application_enables_concurrent_updates(tmp_path):
+def test_application_requires_sequential_updates(tmp_path):
     config = Config(
         telegram_bot_token="123456:ABC-test-token",
         openhands_api_key="k",
@@ -104,7 +109,97 @@ def test_application_enables_concurrent_updates(tmp_path):
         db_path=str(tmp_path / "t.sqlite3"),
     )
     app = build_application(config)
-    assert app.concurrent_updates
+    try:
+        # PTB 22.8: concurrent_updates(False) ⇒ max_concurrent_updates == 1.
+        # A truthiness check would also pass for True (256) and must not be used.
+        assert app.concurrent_updates == 1
+        assert app._update_processor.max_concurrent_updates == 1
+    finally:
+        app.bot_data["db"].close()
+
+
+def test_queue_producers_are_serialized(tmp_path, monkeypatch):
+    """Two concurrent queue producers cannot overlap handler execution.
+
+    This exercises the real PTB update_queue/fetcher path, not direct
+    Application.process_update() calls (which bypass the update processor).
+    """
+    async def run(app, install_bot):
+        events = []
+        started = []
+        active = {"n": 0, "max": 0}
+        first_started = asyncio.Event()
+        second_started = asyncio.Event()
+        release_first = asyncio.Event()
+
+        async def record(update, context):
+            active["n"] += 1
+            active["max"] = max(active["max"], active["n"])
+            started.append(update.update_id)
+            events.append(("start", update.update_id))
+            if len(started) == 1:
+                first_started.set()
+                await release_first.wait()
+            else:
+                second_started.set()
+            events.append(("end", update.update_id))
+            active["n"] -= 1
+
+        app.add_handler(TypeHandler(Update, record), group=-2)
+        updates = [Update(update_id=101), Update(update_id=102)]
+
+        async def producer(update):
+            await app.update_queue.put(update)
+
+        try:
+            await asyncio.gather(*(producer(u) for u in updates))
+            await asyncio.wait_for(first_started.wait(), timeout=2)
+            try:
+                await asyncio.wait_for(second_started.wait(), timeout=0.05)
+            except asyncio.TimeoutError:
+                pass
+            else:
+                pytest.fail("second update started before the first completed")
+            assert len(started) == 1
+            assert active["max"] == 1
+            release_first.set()
+            await asyncio.wait_for(app.update_queue.join(), timeout=2)
+            assert len(started) == 2
+            assert [e[0] for e in events] == ["start", "end", "start", "end"]
+            assert active["max"] == 1
+            assert app.update_queue._unfinished_tasks == 0
+            assert app.update_queue.qsize() == 0
+        finally:
+            release_first.set()
+
+    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))
+
+
+def test_queue_continues_after_handler_exception(tmp_path, monkeypatch):
+    async def run(app, install_bot):
+        seen = []
+        errors = []
+
+        async def record(update, context):
+            seen.append(update.update_id)
+            if update.update_id == 201:
+                raise RuntimeError("boom")
+
+        async def on_error(update, context):
+            errors.append((update.update_id, type(context.error).__name__))
+
+        app.add_handler(TypeHandler(Update, record), group=-2)
+        app.add_error_handler(on_error)
+        await app.update_queue.put(Update(update_id=201))
+        await app.update_queue.put(Update(update_id=202))
+        await asyncio.wait_for(app.update_queue.join(), timeout=2)
+
+        assert seen == [201, 202]
+        assert errors == [(201, "RuntimeError")]
+        assert app.update_queue._unfinished_tasks == 0
+        assert app.update_queue.qsize() == 0
+
+    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))
 
 
 def test_successful_send_records_submission_time_for_watcher(tmp_path):
```

## 10. Handoff checksum

The SHA-256 of this handoff document is recorded in the final response after creation.
