# النشر على Katabump

Katabump المجاني كفاية للبوت ده (308 MB رام، 716 MB تخزين، 25% CPU).
**السيرفر المجاني بيتجدد كل 4 أيام** — لو اتنسي البوت بيقف. حطّ تذكير كل 3 أيام.

## الخطوات

1. من لوحة Katabump اعمل سيرفر جديد نوعه **Python**.
2. ارفع ملفات المشروع (ZIP أو SFTP):
   - `main.py`, `bot/`, `requirements.txt`, `README.md`, `docs/`.
   - ما ترفعش `.env` ولا `.venv/` ولا `*.sqlite3`.
3. اضبط متغيرات البيئة في لوحة السيرفر (Environment Variables):
   - `TELEGRAM_BOT_TOKEN`, `OPENHANDS_API_KEY`, `ALLOWED_TELEGRAM_ID`.
   - اختياري: `OPENHANDS_BASE_URL`, `LOG_LEVEL`, `WATCHER_INTERVAL`.
4. أمر التشغيل: `python main.py` (الحزم تتثبت تلقائيًا من `requirements.txt` أول تشغيل).
5. اضغط **Start**، وتابع السجلات من اللوحة.

## ملاحظات

- الاستقبال long polling، فمفيش منفذ وارد مطلوب.
- التخزين ملف SQLite واحد (`bot_state.sqlite3`) بيتعمل تلقائيًا. لو اتمسح، البوت يبدأ من الأول من غير خسارة (الشاتات نفسها على OpenHands).
- ما تطبعش المفتاح ولا التوكن في السجلات. البوت مش بيسجّل نص البرومتات كامل.

## خطة بديلة

نفس الكود يشتغل على أي VPS أو منصة تانية من غير تعديل:
`pip install -r requirements.txt && python main.py`.
