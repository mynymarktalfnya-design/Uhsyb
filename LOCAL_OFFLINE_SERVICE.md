# الخدمة المحلية والتشغيل دون اتصال

أضيفت خدمة `local-service/mmf_local_service.py` لتوفير طابور دائم مستقل عن تبويب المتصفح. تحفظ الخدمة العمليات في SQLite باستخدام WAL و` synchronous=FULL`، وتستخدم الحالات `pending` و`syncing` و`synced` و`failed`. لا تُزال العملية بعد الإرسال؛ تبقى كسجل محلي حتى بعد نجاح المزامنة، وتبقى العمليات الفاشلة لإعادة المحاولة.

تستخدم الواجهة الخدمة على `http://127.0.0.1:8765` عند توفرها، وتعود تلقائيًا إلى IndexedDB عند عدم تثبيتها. كل عملية تعديل تحمل `X-Operation-ID` و`Idempotency-Key`. في الخادم، يسجل `OperationReceiptMiddleware` الاستجابة الناجحة ويعيدها عند وصول العملية نفسها مرة أخرى، بما يمنع تكرار البيع أو الشراء أو المرتجع عند إعادة الإرسال.

## المزامنة التلقائية

- عند عودة حدث الاتصال `online` تبدأ المزامنة تلقائيًا.
- إذا ظل المتصفح يعتقد أن الاتصال موجودًا بينما الخادم متوقف أو الشبكة غير قابلة للوصول، تعيد الواجهة المحاولة تلقائيًا كل 10 ثوانٍ.
- لا تعمل أكثر من مزامنة واحدة في الوقت نفسه، مع الاحتفاظ بمعرف العملية نفسه أثناء إعادة الإرسال.
- عند استخدام الخدمة المحلية، يتم تمرير جلسة الدخول الحالية إلى `/sync` في الذاكرة فقط حتى تُرسل العمليات المعلقة فورًا.
- يعرض شريط الحالة عدد العمليات غير المكتملة فقط (`pending` و`failed` و`syncing`) ولا يحسب العمليات التي تمت مزامنتها.
- تبقى العمليات الفاشلة محفوظة ولا تُحذف، ويمكن إعادة إرسالها تلقائيًا أو يدويًا من زر المزامنة.

على Windows لا تحفظ الواجهة Access Token في `localStorage` أو IndexedDB؛ يبقى في ذاكرة Renderer فقط. لا يحفظ طابور IndexedDB أو SQLite رؤوس `Authorization` أو Cookies أو Refresh Tokens. عند الحاجة إلى المزامنة بعد إغلاق التطبيق، تستخدم خدمة Windows DPAPI User Scope (`CryptProtectData`/`CryptUnprotectData`) لحماية رمز المصادقة داخل سجل العملية، ولا تحفظه خامًا. إذا لم تتوفر DPAPI على Windows تفشل عملية التخزين بدل حفظ السر مكشوفًا.

تستخدم نسخة Windows ملفًا عشوائيًا `local-service.token` للتخاطب بين Electron وخدمة localhost. ينشئه المثبت داخل `%ProgramData%\MMF\offline\` ويحميه بـACL، وتقرأه الخدمة وElectron فقط. تبقى الخدمة على `127.0.0.1:8765`، وتستخدم `X-MMF-Local-Auth` لمصادقة الطلبات المحلية. لا تعرض نقاط `/queue` رؤوس الطلبات أو body؛ وتعيد حالة العملية و`operation_id` والحقول التشغيلية الضرورية فقط. أما `/health` فيعيد حالة وعدادات مختصرة دون بيانات العمليات.

## Windows

من PowerShell بصلاحيات Administrator:

```powershell
cd local-service
python -m pip install -r requirements.txt
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows.ps1
```

ينشئ المثبت الخدمة `MMFLocalQueueService` ويضبط تشغيلها تلقائيًا مع Windows، ويضع قاعدة البيانات في `%ProgramData%\MMF\offline\offline-queue.sqlite3`. يتطلب التشغيل الفعلي على Windows وجود Python و`pywin32`، ولم يُنفذ اختبار Windows داخل بيئة Linux الحالية.

## Linux

```bash
sudo install -d -m 700 /var/lib/mmf
sudo cp deploy/mmf-local-service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mmf-local-service
```

## نقاط HTTP المحلية

- `GET /health` يعرض عدد العمليات في كل حالة.
- `GET /queue` يعرض ملخص الطابور المحلي فقط، ولا يعرض headers أو body.
- `POST /queue` يضيف عملية، ويمنع تكرار `operation_id`.
- `POST /sync` يطلب مزامنة فورية بالإضافة إلى المزامنة الدورية التلقائية.

## حدود التحقق

تم التحقق محليًا من صياغة Python، وفحص TypeScript، وتشغيل اختبارات وحدة الطابور، ومنع تخزين Authorization الخام، ورفض الأسرار في body وquery string، وعدم إعادة headers أو body من `/queue`. لم يتم الادعاء باختبار ACL أو DPAPI أو خدمة Windows أو إعادة تشغيل Windows فعليًا لأن بيئة التنفيذ Linux. يجب تشغيل اختبار تكاملي على جهاز Windows حقيقي مع خادم قاعدة البيانات الفعلي قبل اعتماد النشر الإنتاجي.
