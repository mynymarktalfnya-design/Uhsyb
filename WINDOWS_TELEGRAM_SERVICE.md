# MMFTelegramBotService

هذه الحزمة تشغّل `scripts/telegram_reports_bot.py` نفسه كخدمة Windows مستقلة، مع تشغيل تلقائي وإعادة تشغيل عند توقف العملية. لا تحتوي الملفات على Token أو Chat ID أو رابط قاعدة بيانات حقيقي.

## الملفات

- `scripts/telegram_service_runner.py`: مشرف الخدمة؛ يحمّل ملف البيئة، يبدأ البوت، يكتب حالة منزوعة الأسرار، ويعيد التشغيل بباكoff يصل إلى خمس دقائق.
- `scripts/windows/install-telegram-service.ps1`: تثبيت الخدمة باستخدام NSSM.
- `scripts/windows/start-telegram-service.ps1`: تشغيل الخدمة.
- `scripts/windows/stop-telegram-service.ps1`: إيقاف الخدمة.
- `scripts/windows/restart-telegram-service.ps1`: إعادة التشغيل.
- `scripts/windows/status-telegram-service.ps1`: عرض حالة Windows وملف الصحة.
- `scripts/windows/uninstall-telegram-service.ps1`: إزالة الخدمة.
- `config/telegram-reports.env.example`: قالب إعدادات غير سري.

## الاسم والحالة

اسم الخدمة هو `MMFTelegramBotService`. تُحفظ الحالة في `%ProgramData%\MMF\telegram-bot-status.json`، والسجلات في `%ProgramData%\MMF\logs\`. الحالات الممكنة هي `STARTING` و`RUNNING` و`ERROR` و`STOPPED`.

## التثبيت

يجب توفير Python وبيئة `.venv` أو تمرير `-PythonPath`، كما يجب توفير `nssm.exe` عبر `-NssmPath` أو متغير البيئة `NSSM_PATH`. انسخ `config/telegram-reports.env.example` إلى `config/telegram-reports.env` على الجهاز المحلي، وضع إعدادات الإنتاج فيه، ثم شغّل PowerShell كمسؤول:

```powershell
.\scripts\windows\install-telegram-service.ps1 -NssmPath C:\Tools\nssm\win64\nssm.exe
.\scripts\windows\start-telegram-service.ps1
.\scripts\windows\status-telegram-service.ps1
```

ملف الإعداد الحقيقي مستثنى من Git، ولا يجوز وضعه في المستودع. الخدمة لا تعتمد على تشغيل المتصفح أو واجهة النظام.
