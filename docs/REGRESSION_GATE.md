# بوابة الانحدار (Regression Gate)

أي تغيير في الكود لازم يعدّي البوابة دي قبل ما يندمج في `main`. نفس الخطوات بتشتغل
تلقائيًا في GitHub Actions (`.github/workflows/ci.yml`) على Python 3.11 و3.13.

## الخطوات (بالترتيب)

```bash
pip install -r requirements-dev.txt
python -m pyflakes bot/ main.py tests/   # فحص ثابت: مفيش imports/متغيرات ميتة
python -m pytest -q                      # كل الاختبارات لازم تعدّي
```

## معايير القبول

1. **فحص ثابت نضيف**: `pyflakes` ما يطلّعش أي تحذير على `bot/` و`main.py` و`tests/`.
2. **كل الاختبارات خضراء**: `pytest` بيعدّي كامل من غير أي فشل/خطأ.
3. **مفيش أسرار في الكود**: التوكنات والمفاتيح متغيرات بيئة بس (راجع قسم الأمان في README).
4. **مفيش كتابة كاملة لسجل ممكن يكون قديم**: أي تحديث لحقل واحد يستخدم
   `UPDATE ... WHERE id=:id` ضيّق (مش استبدال الصف كامل).

## تشغيل محلي سريع

```bash
python -m pytest -q tests/test_outbox.py tests/test_grouping.py   # صندوق الصادر والتجميع
python -m pytest -q tests/test_config.py                          # الإعدادات (مستخدم واحد)
python -m pytest -q tests/test_db_maintenance.py                  # تكامل قاعدة البيانات
```

## ملاحظات

- الاختبارات بتشتغل على `sqlite :memory:` أو ملفات مؤقتة — مفيش اعتماد على شبكة أو خدمات خارجية.
- لو أضفت لغة/ميزة جديدة، اتأكد إن اختباراتها بتغطّي الحالات السلبية كمان (مش المسار السعيد بس).
