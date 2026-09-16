# MMF Windows Production Packaging

هذه الحزمة تبني تطبيقًا مكتبيًا Native باسم **ميني ماركت الفنية** باستخدام Electron. الواجهة تُحمّل داخل `BrowserWindow` ولا تستدعي Chrome أو Edge أو المتصفح الافتراضي. الرابط المحلي مخفي داخل التطبيق فقط.

## بناء Installer على Windows

يتطلب جهاز بناء Windows x64 مثبتًا عليه Node.js، pnpm، Python 3.11+، وPyInstaller:

```powershell
pnpm install
python -m pip install pyinstaller pywin32
pnpm run desktop:dist
```

يُنتج الملف:

```text
release\MiniMarketAlfnya-Setup-0.0.0.exe
```

تُبنى runtimes أولًا بواسطة `packaging/windows/build-runtime.ps1`. لا تعتمد النسخة المثبتة على Python أو Node المثبتين لدى المستخدم بعد تضمين binaries.

## الإعدادات والبيانات

انسخ `config/production.env.example` إلى:

```text
%ProgramData%\MMF\config\production.env
```

ثم ضع قيم قاعدة البيانات وJWT وTelegram على جهاز العميل فقط. لا تُضمّن القيم الحقيقية في GitHub أو Installer أو JavaScript bundle.

بيانات Offline تحفظ في:

```text
%ProgramData%\MMF\offline\offline-queue.sqlite3
```

ولا يحذف Uninstall هذه البيانات.

## الخدمات

بعد التثبيت شغّل PowerShell كمسؤول مرة واحدة لتثبيت الخدمة المحلية:

```powershell
.\packaging\windows\install-mmf-services.ps1 -InstallRoot $PWD
```

تُثبت `MMFLocalQueueService` لتبدأ تلقائيًا، وتُثبت خدمة Telegram فقط عند تمرير NSSM وملف إعداد حقيقي:

```powershell
.\packaging\windows\install-mmf-services.ps1 -InstallRoot $PWD -NssmPath C:\Tools\nssm\nssm.exe
```

## حدود التحقق

لا يُعتبر Installer مُختبرًا إنتاجيًا إلا بعد بنائه وتشغيله على جهاز Windows نظيف: تثبيت، اختصار Desktop وStart Menu، تشغيل بدون Chrome، Restart Windows، Offline/Sync، POS، ثم Uninstall/Reinstall دون حذف بيانات `%ProgramData%\MMF`.
