# تثبيت حزمة ميني ماركت الفنية على Windows

هذه الحزمة لا تحتوي على Tokens أو روابط قواعد بيانات أو ملفات أسرار. استخدم قاعدة اختبار منفصلة، وليس قاعدة الإنتاج.

## تشغيل واجهة Production

لا تفتح `index.html` مباشرة ولا تستخدم `pnpm dev` لتشغيل النسخة النهائية؛ استخدم المشغل التالي من جذر مجلد `Uhsyb`:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start-production-windows.ps1
```

ثم افتح `http://localhost:5173/login`. يشغل المشغل Backend على المنفذ 8080، ويقدم ملفات CSS/JavaScript المبنية، ويمرر طلبات `/api` إلى Backend. يجب توفير `JWT_SECRET_KEY` بطول 32 حرفًا على الأقل و`NEON_DATABASE_URL` أو `MONGO_URL` عبر متغيرات Windows/Secret Manager.

إذا كان `dist/public/index.html` غير موجود، نفّذ `pnpm install --frozen-lockfile` ثم `pnpm --filter @workspace/market-frontend build`.

## التثبيت السريع بنقرة واحدة

1. فك ضغط ملف ZIP كاملًا.
2. افتح مجلد `Uhsyb`.
3. اضغط مرتين على الملف:

```text
install-windows.cmd
```

4. وافق على نافذة صلاحيات Windows إذا ظهرت.

سيقوم الملف تلقائيًا بـ:

- طلب صلاحيات Administrator.
- تشغيل مثبت الخدمة.
- تثبيت `pywin32`.
- إنشاء خدمة `MMFLocalQueueService`.
- ضبط تشغيلها تلقائيًا مع Windows.
- إنشاء قاعدة الطابور في `%ProgramData%\MMF\offline\offline-queue.sqlite3`.

اترك نافذة التثبيت مفتوحة حتى تظهر رسالة إتمام التثبيت.

## التحقق من الخدمة

افتح PowerShell كمسؤول وشغّل:

```powershell
Get-Service -Name MMFLocalQueueService
```

يجب أن تكون الحالة `Running` وأن يكون نوع بدء التشغيل تلقائيًا.

## التثبيت اليدوي البديل

إذا منع Windows تشغيل ملف CMD، افتح PowerShell كمسؤول ثم:

```powershell
cd .\local-service
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows.ps1
```

## إعداد Telegram وقاعدة الاختبار

لا تضع القيم داخل المشروع. عيّنها في جلسة PowerShell محلية فقط:

```powershell
$env:TELEGRAM_BOT_TOKEN = "ضع القيمة محليًا"
$env:TELEGRAM_CHAT_ID = "ضع القيمة محليًا"
$env:TELEGRAM_ALLOWED_CHAT_IDS = "ضع القيمة محليًا"
$env:MONGO_URL = "رابط قاعدة الاختبار"
$env:DB_NAME = "market_test"
$env:REPORTS_TIMEZONE = "Asia/Aden"
$env:ALLOW_MONGOMOCK = "false"
$env:JWT_SECRET_KEY = "مفتاح اختبار محلي طويل"
```

تحقق من وجود الإعدادات دون طباعة قيمها:

```powershell
@("TELEGRAM_BOT_TOKEN","TELEGRAM_CHAT_ID","MONGO_URL","DB_NAME") | ForEach-Object {
  Write-Host "$_=" + $(if ([Environment]::GetEnvironmentVariable($_)) { "present" } else { "missing" })
}
```

## تشغيل البوت

```powershell
cd .\Uhsyb
python .\scripts\telegram_reports_bot.py
```

استخدم Bot اختبار وحساب Telegram مصرحًا به فقط. لا تستخدم بيانات الإنتاج.

## الاختبار

اختبر إعادة تشغيل Windows، وانقطاع الإنترنت، وبقاء العمليات Pending، والمزامنة، وعدم تكرار Operation ID، وتقارير Telegram وPDF. لا ترفع ملفات الأسرار إلى GitHub.
