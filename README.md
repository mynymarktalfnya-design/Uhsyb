# نظام إدارة الميني ماركت



نظام عربي لإدارة عمليات الميني ماركت والفرع، مع واجهة تشغيل للموظفين وواجهة خلفية لإدارة المستخدمين، المنتجات، المبيعات، المصروفات، الحسابات، التقارير، النسخ الاحتياطية، وسجل التدقيق.



المستودع الرسمي: [mynymarktalfnya-design/Uhsyb](https://github.com/mynymarktalfnya-design/Uhsyb)



## المزايا الرئيسية



يدعم المشروع تسجيل الدخول وإدارة الصلاحيات، إدارة المنتجات والتصنيفات، إدارة العملاء والموردين، تسجيل المبيعات ومردودات المبيعات، متابعة المصروفات، الحسابات المدينة والدائنة، التقارير، الإشعارات، إغلاق اليوم، النسخ الاحتياطية، وسجل العمليات. كما يتضمن آلية مزامنة وسياقًا لتشغيل النظام في وضع الاختبار أو وضع الإنتاج.



## البنية التقنية



| الجزء | التقنية |

|---|---|

| واجهة المستخدم | React، Vite، TypeScript/JavaScript، Tailwind CSS، Radix UI |

| خادم API الرئيسي | Python، FastAPI، Uvicorn |

| خادم API المساند | Node.js، TypeScript، Express |

| قواعد البيانات | MongoDB أو Neon PostgreSQL بحسب الإعداد |

| إدارة حزم JavaScript | pnpm workspaces |

| التحقق من البيانات | Pydantic وZod |

| التقارير والملفات | jsPDF وjsPDF AutoTable وhtml2canvas |



## هيكل المشروع



```text

.

├── artifacts/

│   ├── market-frontend/     # واجهة نظام إدارة الميني ماركت

│   ├── api-server/          # خادم API المساند المبني بـ TypeScript

│   └── mockup-sandbox/      # بيئة تجارب النماذج والواجهات

├── market-backend/          # خادم FastAPI الرئيسي ووحدات قاعدة البيانات

│   ├── routes/              # مسارات المصادقة والكتالوج والمبيعات والتقارير وغيرها

│   ├── server.py            # نقطة تشغيل تطبيق FastAPI

│   ├── database.py          # تهيئة اتصال قاعدة البيانات

│   ├── run.sh               # تشغيل التطوير

│   └── run_prod.sh          # تشغيل الإنتاج

├── scripts/                 # سكربتات وأدوات مساحة العمل

├── attached_assets/         # ملفات وصور مرفقة مستخدمة في المشروع

├── main.py                  # نقطة دخول إضافية للمشروع

├── package.json             # أوامر مساحة عمل pnpm

├── pnpm-workspace.yaml      # تعريف مساحة العمل

├── pyproject.toml           # تعريف تبعيات Python العامة

└── README.md

```



## المتطلبات



يحتاج المشروع إلى Node.js، وpnpm، وPython 3.11 أو أحدث. ويحتاج الخادم الخلفي إلى MongoDB أو Neon PostgreSQL عند التشغيل باستخدام قاعدة بيانات دائمة.



| الأداة | الإصدار أو الشرط |

|---|---|

| Node.js | الإصدار المستخدم في بيئة المشروع، ويفضل Node.js 24 |

| pnpm | مطلوب؛ يرفض المشروع استخدام npm وyarn في مرحلة التثبيت |

| Python | 3.11 أو أحدث |

| MongoDB | اختياري عند استخدام Neon PostgreSQL |

| Neon PostgreSQL | اختياري عند استخدام MongoDB |



## التثبيت



استنسخ المستودع ثم ثبّت تبعيات JavaScript وPython:



```bash

git clone https://github.com/mynymarktalfnya-design/Uhsyb.git

cd Uhsyb

pnpm install

python3 -m venv .venv

source .venv/bin/activate

pip install -r market-backend/requirements.txt

```



يمكن استخدام `uv sync` بدلًا من إنشاء البيئة الافتراضية يدويًا إذا كانت أداة `uv` متاحة:



```bash

uv sync

```



## إعداد متغيرات البيئة



أنشئ ملف `.env` محليًا، ولا ترفعه إلى GitHub. يقرأ الخادم الخلفي المتغيرات التالية:



| المتغير | الوصف | القيمة الافتراضية أو الملاحظة |

|---|---|---|

| `NEON_DATABASE_URL` | رابط اتصال Neon PostgreSQL | إذا كان موجودًا يُستخدم بدل MongoDB |

| `MONGO_URL` | رابط اتصال MongoDB | مطلوب عند عدم استخدام Neon |

| `DB_NAME` | اسم قاعدة بيانات MongoDB | `market_db` |

| `ALLOW_MONGOMOCK` | السماح بقاعدة بيانات مؤقتة داخل الذاكرة | استخدم `true` للتجارب المحلية فقط |

| `ADMIN_EMAIL` | بريد حساب المدير الأول | `admin@market.com` |

| `ADMIN_PASSWORD` | كلمة مرور حساب المدير الأول | مطلوبة في بيئة الإنتاج؛ لا توجد قيمة إنتاجية افتراضية آمنة |

| `BACKUP_DIR` | مجلد حفظ النسخ الاحتياطية | اختياري |

| `PORT` | منفذ الخدمة | يستخدمه سكربت التشغيل، والافتراضي للخلفية `8080` |

| `REACT_APP_BACKEND_URL` | عنوان الخادم الخلفي الذي تستعمله الواجهة | اتركه فارغًا إذا كانت الواجهة والخلفية على نفس العنوان |
| `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON` | بيانات حساب خدمة Google بصيغة JSON | اختياري؛ يُحفظ كسر في بيئة التشغيل ولا يرفع إلى Git |
| `GOOGLE_DRIVE_ACCESS_TOKEN` | بديل مؤقت لرمز وصول Google Drive | اختياري؛ لا يُحفظ في الواجهة |
| `GOOGLE_DRIVE_BACKUP_FOLDER_ID` | معرّف مجلد Drive المخصص للنسخ | اختياري؛ يرفع إلى جذر Drive إذا تُرك فارغًا |
| `TELEGRAM_BOT_TOKEN` | رمز بوت Telegram | سري؛ لا تضعه في Git أو الواجهة |
| `TELEGRAM_CHAT_ID` | المحادثة التي تستقبل إشعارات النظام | مثال: `8227840392` |
| `JWT_SECRET_KEY` | مفتاح توقيع جلسات JWT | مطلوب، بطول 32 محرفًا على الأقل؛ لا تحفظه في Git |
| `PGPASSWORD` | اعتماد سكربتات PostgreSQL القديمة | مطلوب فقط عند استخدام سكربت PostgreSQL؛ لا تحفظه في Git |



مثال إعداد محلي غير حقيقي:



```env

NEON_DATABASE_URL=

MONGO_URL=mongodb://localhost:27017

DB_NAME=market_db

ALLOW_MONGOMOCK=true

ADMIN_EMAIL=admin@example.com

ADMIN_PASSWORD=غيّر-هذه-القيمة

BACKUP_DIR=./backups

PORT=8080

REACT_APP_BACKEND_URL=http://localhost:8080

```



> لا تضع كلمات مرور أو مفاتيح أو روابط قواعد بيانات حقيقية داخل `README.md` أو أي commit عام.
> 
> **Google Drive والنسخ الآمن:** عند إعداد بيانات اعتماد Google Drive، يتحقق النظام من الاتصال الفعلي فقط. يستخدم بصمة SHA-256 لمحتوى كل ملف ويضعها في `appProperties.backup_signature` داخل Drive؛ لذلك لا يرفع النسخة نفسها مرتين. الاستعادة تتطلب كلمة مرور المدير، وتنزيلًا مؤقتًا وفحصًا للنسخة وإنشاء نسخة أمان، ثم تمنع استعادة البصمة نفسها مرة أخرى. يمكن تفعيل الرفع التلقائي من إعدادات النسخ، أو تنفيذ المزامنة يدويًا عند الحاجة.
>
> **إشعار عودة الإنترنت:** يفحص الخادم المحلي الاتصال كل دقيقة. عند الانتقال من Offline إلى Online يرسل إشعارًا إلى Telegram، ثم يزامن النسخ غير المرفوعة إلى Google Drive إذا كان الرفع التلقائي مفعّلًا، ويرسل نتيجة المزامنة. لا يتم تكرار الإشعار إلا بعد حدوث انقطاع جديد.

### المراقب المستقل عن خادم التطبيق

يوجد سكربت مستقل في `scripts/internet_telegram_monitor.py`. لا يعتمد على FastAPI أو قاعدة البيانات، ويحفظ حالته ذريًا حتى لا يكرر إشعار الانتقال نفسه. للاختبار اليدوي:

```bash
export TELEGRAM_BOT_TOKEN='رمز-جديد-وسري'
export TELEGRAM_CHAT_ID='8227840392'
export STATE_FILE=/tmp/mabna-connectivity-state.json
python3 scripts/internet_telegram_monitor.py --once --notify-now
```

للتشغيل الدائم على جهاز Linux، انسخ `deploy/telegram-monitor.env.example` إلى `/etc/mabna-market/telegram-monitor.env`، ضع الرمز الجديد، ثم نفّذ:

```bash
sudo install -d -m 700 /etc/mabna-market /var/lib/mabna-market
sudo chmod 600 /etc/mabna-market/telegram-monitor.env
sudo cp deploy/internet-telegram-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now internet-telegram-monitor
sudo systemctl status internet-telegram-monitor
```

عرض السجل:

```bash
journalctl -u internet-telegram-monitor -f
```

### بوت التقارير التفاعلي

يوجد بوت تقارير تفاعلي مستقل في `scripts/telegram_reports_bot.py` ويخدم `TELEGRAM_CHAT_ID` المصرح به فقط، ويمكن توسيع قائمة المستخدمين المصرح لهم عبر `TELEGRAM_ALLOWED_CHAT_IDS`. يعتمد البوت على نفس قاعدة البيانات ودوال التقارير والحسابات المستخدمة في الخادم، ولا ينشئ حسابات أو أرقامًا محاسبية موازية. يدعم `/menu` أو `/inventory`، ثم يقدّم القائمة التفاعلية التالية:

```text
📊 المبيعات        يومي / شهري
🛒 المشتريات       يومي / شهري
💰 الأرباح         يومي / شهري
👥 حسابات العملاء  اختيار العميل والفترة
🏪 حسابات التجار   اختيار التاجر والفترة
📦 جرد المخزون     PDF مطابق لقالب النظام
💸 المصروفات       يومي / شهري
```

تظهر أزرار Inline لاختيار التقرير والفترة والعميل أو التاجر مع Pagination وبحث بالاسم. التقارير المالية تستدعي دوال `routes/reports.py` وكشوف الحسابات الموجودة في الخادم مباشرة، بينما يستخدم تقرير الجرد مولد `inventory_audit_report.py` نفسه. ترسل التقارير الطويلة كـ PDF. لتشغيله، انسخ `deploy/telegram-reports.env.example` إلى ملف أسرار منفصل، ثبّت تبعيات Python، ثم ثبّت `deploy/telegram-reports-bot.service` باستخدام systemd. لا تشغّل البوت على قاعدة بيانات تجريبية `mongomock` لأن بياناتها مؤقتة.


## التشغيل المحلي



### تشغيل الخادم الخلفي



```bash

cd market-backend

./run.sh

```



يشغّل هذا الأمر تطبيق FastAPI باستخدام Uvicorn مع إعادة التحميل التلقائي. ويمكن تشغيله يدويًا من جذر المشروع كما يلي:



```bash

cd market-backend

uvicorn server:app --host 0.0.0.0 --port 8080 --reload

```



### تشغيل واجهة المستخدم



في طرفية ثانية:



```bash

pnpm --filter @workspace/market-frontend run dev

```



تحتاج Vite إلى متغير `PORT` عند تشغيل الواجهة. إذا لم يكن محددًا في بيئتك، عيّنه قبل التشغيل:



```bash

PORT=5173 pnpm --filter @workspace/market-frontend run dev

```



### تشغيل خادم API المساند



```bash

PORT=5000 pnpm --filter @workspace/api-server run dev

```



## البناء والتحقق



نفّذ أوامر التحقق من جذر المشروع:



```bash

pnpm run typecheck

pnpm run build

```



وللتحقق من حزم محددة:



```bash

pnpm --filter @workspace/market-frontend run typecheck

pnpm --filter @workspace/api-server run typecheck

pnpm --filter @workspace/market-frontend run build

pnpm --filter @workspace/api-server run build

```



## فحص صحة الخادم



بعد تشغيل الخادم الخلفي، يمكن فحص حالته عبر:



```bash

curl http://localhost:8080/api/health

```



كما يعرض المسار التالي معلومات أساسية عن التطبيق:



```bash

curl http://localhost:8080/api/

```
