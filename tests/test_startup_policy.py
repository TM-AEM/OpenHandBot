"""TASK 04B-07: سياسة تحديثات تيليجرام المتراكمة عند البدء (القرار 3).

عند تشغيل البوت بنـ long polling، أي تحديثات واردة اتراكمت وقت التوقف لازم تتتجاهل
(drop_pending_updates=True) عشان البوت مايعالجش أوامر قديمة عند الرجوع. ده منفصل تمامًا
عن تعافي الصندوق الصادر (outbox) — اللي لازم يحافظ على السجلات الدائمة ومايحذفهاش.

بنختبر مسار الإعداد الحقيقي (main.main) من غير أي polling حقيقي أو اتصال تيليجرام.
"""
import bot.app as app_mod
import main as main_mod


class _RecordingApp:
    """تطبيق وهمي بيسجّل باراميترات run_polling من غير أي شبكة."""

    def __init__(self):
        self.polling_kwargs = None

    def run_polling(self, **kwargs):
        self.polling_kwargs = kwargs


def test_main_configures_drop_pending_updates(monkeypatch, tmp_path):
    # نبني Config حقيقي من بيئة مغلقة (بدون أي أسرار حقيقية).
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "OPENHANDS_API_KEY": "sk-test-not-real",
        "ALLOWED_TELEGRAM_ID": "1",
        "DB_PATH": str(tmp_path / "t.sqlite3"),
    }
    monkeypatch.setattr("bot.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", env["TELEGRAM_BOT_TOKEN"])
    monkeypatch.setenv("OPENHANDS_API_KEY", env["OPENHANDS_API_KEY"])
    monkeypatch.setenv("ALLOWED_TELEGRAM_ID", env["ALLOWED_TELEGRAM_ID"])
    monkeypatch.setenv("DB_PATH", env["DB_PATH"])

    fake_app = _RecordingApp()
    # نعترض بناء التطبيق عند نقطة استخدام main، ونرجّع تطبيق وهمي.
    monkeypatch.setattr(main_mod, "build_application", lambda config: fake_app)

    rc = main_mod.main()

    assert rc == 0
    assert fake_app.polling_kwargs is not None
    assert fake_app.polling_kwargs.get("drop_pending_updates") is True


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
