"""OHB2-STAGE2: سياسة تحديثات تيليجرام المتراكمة عند البدء (D2).

**تغيير مقصود (Stage 2، موافقة صريحة):** بدل `run_polling(drop_pending_updates=True)` (اللي
كان **يرمي** المعلّق)، بقت حلقة الاستطلاع المخصّصة تستخدم `deleteWebhook(drop_pending_updates=False)`
وتستأنف من الحدّ الدائم (`B+1`) أو `offset=None` ⇒ **المعلّق محفوظ دائمًا** (مفيش رمي تلقائي).
هذا منفصل تمامًا عن تعافي الصندوق الصادر (outbox) — اللي لازم يحافظ على السجلات الدائمة.

بنختبر مسار الإعداد الحقيقي (`main.main`) من غير أي polling حقيقي أو اتصال تيليجرام.
"""
import bot.app as app_mod
import main as main_mod


class _RecordingApp:
    """تطبيق وهمي بيسجّل نقطة الإقلاع من غير أي شبكة."""

    def __init__(self):
        self.polling_kwargs = None
        self.ran_custom_bot = False

    def run_polling(self, **kwargs):  # pragma: no cover — ممنوع الاستخدام في Stage 2
        self.polling_kwargs = kwargs


def _env(monkeypatch, tmp_path):
    monkeypatch.setattr("bot.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setenv("OPENHANDS_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("ALLOWED_TELEGRAM_ID", "1")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.sqlite3"))


def test_main_uses_custom_poller_not_run_polling(monkeypatch, tmp_path):
    """main لازم يشغّل الحلقة المخصّصة (`run_bot`)، **مش** `run_polling` (مفيش Updater)."""
    _env(monkeypatch, tmp_path)

    fake_app = _RecordingApp()
    monkeypatch.setattr(main_mod, "build_application", lambda config, **kwargs: fake_app)

    async def _fake_run_bot(application):
        application.ran_custom_bot = True

    monkeypatch.setattr(main_mod, "run_bot", _fake_run_bot)

    rc = main_mod.main()

    assert rc == 0
    assert fake_app.ran_custom_bot is True
    # ممنوع مسار `run_polling` القديم (اللي كان بيرمي المعلّق).
    assert fake_app.polling_kwargs is None


def test_drop_pending_is_independent_of_outbox_recovery(monkeypatch, tmp_path):
    """إسقاط التحديثات الواردة مايحذفش سجلات الصندوق الدائمة.

    نبني تطبيق حقيقي (بدون polling) ونضيف سجل pending قبل التعافي، ونتأكد إن التعافي
    سابه زي ما هو (الـ worker هو اللي هيعالجه) — يعني السياسة الواردة والعمل الصادر
    مسارين منفصلين.
    """
    from bot.app import build_application
    from bot.config import Config

    config = Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )
    app = build_application(config)
    db = app.bot_data["db"]
    oid = db.add_outbox("c1", 1, "برومت مهم", "t")
    assert db.count_outbox("pending") == 1

    # تعافي الصندوق (نفس اللي بيحصل في post_init) — بدون تشغيل أي worker/polling.
    import asyncio
    asyncio.run(app_mod.handlers.outbox_recover(app))

    # السجل الدائم لسه موجود ومالمتسش.
    item = db.get_outbox(oid)
    assert item is not None
    assert item.status == "pending"
    db.close()
