# بوابة الانحدار (Regression Gate)

أي تغيير في الكود لازم يعدّي البوابة دي قبل ما يندمج في `main`. نفس الخطوات بتشتغل
تلقائيًا في GitHub Actions (`.github/workflows/ci.yml`) على Python 3.11 و3.13.

## الخطوات (بالترتيب)

```bash
pip install -r requirements-dev.txt
python -m pyflakes bot/ automation/ main.py tests/  # فحص ثابت: مفيش imports/متغيرات ميتة
python -m pip_audit -r requirements-dev.txt                # فحص أمني للتبعيات (SCA)
python -m bandit -r bot/ automation/ main.py -lll -s B613  # فحص أمني ثابت للكود (SAST)
python -m pytest -q                                        # كل الاختبارات لازم تعدّي
node --test tests/frontend/*.test.js                       # اختبارات الواجهة
```

## معايير القبول

1. **فحص ثابت نضيف**: `pyflakes` ما يطلّعش أي تحذير على `bot/` و`automation/`
   و`main.py` و`tests/`.
2. **كل الاختبارات خضراء**: `pytest` و`node --test` بيعدّوا كامل من غير أي فشل/خطأ.
3. **مفيش ثغرات تبعيات معروفة**: `pip-audit` يرجّع «No known vulnerabilities found».
4. **مفيش نتائج SAST عالية الخطورة**: `bandit -r bot/ automation/ main.py -lll -s B613`
   يخرج بصفر (B613 = محارف bidi مقصودة في التعليقات العربية، مش trojan-source). النطاق
   بيغطّي `automation/` كمان (AUD-07).
5. **مفيش أسرار في الكود**: التوكنات والمفاتيح متغيرات بيئة بس (راجع قسم الأمان في README).
6. **مفيش كتابة كاملة لسجل ممكن يكون قديم**: أي تحديث لحقل واحد يستخدم
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
