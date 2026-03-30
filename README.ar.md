# TikTok Device Generator — التوثيق بالعربية

**المستودع:** [github.com/code-root/TikTokDeviceGenerator](https://github.com/code-root/TikTokDeviceGenerator) · **الإصدارات:** [كل الإصدارات](https://github.com/code-root/TikTokDeviceGenerator/releases) · **الأحدث:** [v1.0.0](https://github.com/code-root/TikTokDeviceGenerator/releases/tag/v1.0.0)

أداة سطح مكتب (واجهة **Tkinter**) لتوليد بيانات تسجيل جهاز وإرسالها إلى واجهة **device register** الخاصة بتطبيق TikTok، ثم حفظ النتائج في ملفات **JSON** مع دعم **الدُفعات**، **تعدد الخيوط**، و**البروكسي** الاختياري.

**التوثيق:** **[English — README.md](README.md)** · **عربي** (هذا الملف)

> **تنبيه:** استخدم الأداة وفق سياسات الخدمة والقوانين المعمول بها. هذا المستند يشرح السلوك التقني فقط ولا يشجع على أي استخدام غير مصرح به.

**وسوم وكلمات مفتاحية (تيك توك):** **إنشاء الحسابات** وخطوة **ربط الجهاز**، واجهة **`device_register`**, **`device_id` / `install_id` (IID)**، **توقيع/تجهيز حمولة التسجيل** (Java ومكتبات أصلية عبر unidbg)، **تسجيل أجهزة بالدُفعات**، أتمتة مع **بروكسي**. على GitHub تُضاف للمستودع مواضيع مثل `account-creation` و`device-registration` و`request-signing` و`tiktok-api` وغيرها لتسهيل العثور على المشروع.

---

## جدول المحتويات

1. [ما الذي تفعله الأداة؟](#ما-الذي-تفعله-الأداة)
2. [المتطلبات](#المتطلبات)
3. [التثبيت](#التثبيت)
4. [تشغيل البرنامج](#تشغيل-البرنامج)
5. [الإصدارات (Releases)](#الإصدارات-releases)
6. [هيكل المشروع والملفات المهمة](#هيكل-المشروع-والملفات-المهمة)
7. [شرح واجهة المستخدم](#شرح-واجهة-المستخدم)
8. [أماكن حفظ الملفات وتنسيق JSON](#أماكن-حفظ-الملفات-وتنسيق-json)
9. [البروكسي](#البروكسي)
10. [Java والمكتبات الأصلية](#java-والمكتبات-الأصلية)
11. [استكشاف الأعطال](#استكشاف-الأعطال)
12. [الاعتمادات](#الاعتمادات)
13. [المطوّر والشركة والتواصل](#المطور-والشركة-والتواصل)
14. [دعم المشروع](#دعم-المشروع)

---

## ما الذي تفعله الأداة؟

1. **توليد مدخلات عشوائية** (مثل `openudid`، معرّفات زمنية، نمط MAC، إلخ) وتمريرها إلى **Java** عبر **`unidbg.jar`** داخل مجلد `Libs/` مع تحميل المكتبات المناسبة لنظامك من `Libs/prebuilt/<منصة>/`.
2. **استخراج حمولة ثنائية** من مخرجات unidbg (تنسيق `hex=…` في stdout).
3. إرسال **POST** إلى `https://log-va.tiktokv.com/service/2/device_register/` مع ترويسات محددة ونوع المحتوى `application/octet-stream;tt-data=a`.
4. عند نجاح الاستجابة JSON، تخزين **`device_id`** و **`install_id`** (والنصوص المقابلة إن وُجدت) مع بيانات إضافية عن الطلب والشبكة.
5. في وضع **الدفعة**: تشغيل عدة أجهزة بالتوازي عبر **`ThreadPoolExecutor`** مع إمكانية **إيقاف** التشغيل قبل اكتمال كل المهام.

---

## المتطلبات

| المكوّن | الوصف |
|--------|--------|
| **Python** | إصدار يدعم الصيغة الحديثة. يُنصح بـ **Python 3.10+**. |
| **حزم Python** | مذكورة في `requirements.txt` — الأهم: **`requests[socks]`** لدعم بروكسي SOCKS. |
| **Java** | JVM قادرة على تشغيل **`Libs/unidbg.jar`**. على **Windows 64-bit** يجب أن تكون Java **64-bit** لتتوافق مع **`Libs/prebuilt/win64/`**. |
| **ملفات المشروع** | وجود **`Libs/unidbg.jar`** ومجلد **`Libs/prebuilt/<منصة>/`** المناسب (مثل `win64`، `linux64`، `osx64`). |

---

## التثبيت

1. استنساخ أو تنزيل المشروع وفك الضغط إن لزم.
2. إنشاء بيئة افتراضية (اختياري):

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. تثبيت الاعتمادات:

   ```bash
   pip install -r requirements.txt
   ```

4. التأكد من تثبيت **JDK/JRE** وتشغيل `java -version`. على Windows، إن وُجدت Java 32-bit فقط بينما المشروع يستخدم مكتبات **win64**، فستفشل العملية — راجع قسم [Java والمكتبات الأصلية](#java-والمكتبات-الأصلية).

---

## تشغيل البرنامج

```bash
python DeviceGenerator.py
```

لا يوجد وضع سطر أوامر منفصل؛ كل الإعدادات من الواجهة الرسومية.

راجع قسم **[الإصدارات (Releases)](#الإصدارات-releases)** لتنزيل إصدارات مُعلَّمة أو ملفات جاهزة عند نشرها.

---

## الإصدارات (Releases)

كل الإصدارات المُعلَّمة والملاحظات والمرفقات: **[github.com/code-root/TikTokDeviceGenerator/releases](https://github.com/code-root/TikTokDeviceGenerator/releases)**

- **آخر وسم:** [v1.0.0](https://github.com/code-root/TikTokDeviceGenerator/releases/tag/v1.0.0)
- عند نشر ملف **`.exe`** جاهز سيظهر ضمن **Assets** في صفحة الإصدار؛ غالباً ما تبقى حاجة لمجلد **`Libs/`** و**Java** ما لم يذكر خلاف ذلك في وصف الإصدار.

---

## هيكل المشروع والملفات المهمة

```
TikTokDeviceGenerator-main/
├── DeviceGenerator.py      # البرنامج الرئيسي (واجهة + منطق الدفعة + الطلبات)
├── requirements.txt
├── README.md               # التوثيق بالإنجليزية
├── README.ar.md              # هذا الملف (العربية)
├── assets/                   # صور QR للدعم / الإيداع
├── scripts/                  # مثل verify_environment.py
├── Libs/
│   ├── unidbg.jar
│   └── prebuilt/
├── Device/
└── generated_devices/
```

ثوابت مهمة في الكود:

- **`DEVICES_PER_JSON_FILE = 50`**: عدد السجلات في كل ملف تحت `Device/`.
- **`DEVICE_REGISTER_URL`**: عنوان طلب التسجيل.

---

## شرح واجهة المستخدم

### شريط العنوان والرأس

- يعرض اسم الأداة ومعلومات مختصرة عن الدفعة والبروكسي والتصدير.

### أزرار التحكم العلوية

- **Start**: يبدأ دفعة جديدة بعد التحقق من المسارات (`unidbg.jar`، `Libs/prebuilt/<منصة>`)، العدد، الخيوط، وصحة البروكسي إن وُجد.
- **Stop**: يطلب إيقاف التشغيل؛ المهام الجارية قد تكتمل، ويُلغى انتظار البقية. تُحدَّث التقدم والملخص وفق ما اكتمل فعلياً.
- **Open output folder**: يفتح مجلد **Output folder** الحالي في مستكشف الملفات (على Windows عبر `os.startfile`).

### خيارات الدفعة (Batch options)

- **Number of devices**: عدد الأجهزة المطلوب توليدها في الدفعة (1–9999).
- **Threads**: عدد الخيوط المتوازية (1–64)، ويُقيَّد تلقائياً بحيث لا يتجاوز عدد الأجهزة.
- **Output folder**: مسار يُعرض في الحقل ويُفتح عند الضغط على **Open output folder**.  
  **ملاحظة تقنية:** في الإصدار الحالي من `DeviceGenerator.py` تُكتب ملفات الأجهزة دائماً في **`<مجلد_المشروع>/Device/`** وملخصات الدُفعات في **`<مجلد_المشروع>/generated_devices/`** بغض النظر عن قيمة هذا الحقل.
- **Proxy URL (optional)**: بروكسي اختياري لجميع طلبات `device_register` في الدفعة.

### معاينة آخر جهاز ناجح (Last device)

- حقول **OpenUDID**، **Device ID**، **IID** (install id) للقراءة فقط، مع أزرار **Copy** لكل حقل. تُحدَّث عند آخر تسجيل **ناجح** في الدفعة الحالية.

### التقدم والحالة

- شريط تقدم (بداية غير محددة أثناء «التحضير»، ثم محدد حسب `منجز/الإجمالي`).
- سطر يجمع **النسبة/العدد** مع **رسالة الحالة** القصيرة.

### السجل (Log)

- يعرض لكل جهاز (عند توفره) تفاصيل الطلب: العنوان، الترويسات، معاينة **hex** لجسم الطلب، ثم الاستجابة أو رسالة الخطأ.  
- عند الكتابة إلى ملفات **`Device/devices_*.json`** يُزال حقل **`request_log`** من السجل المخزَّن لتقليل حجم الملف؛ السجل يبقى للواجهة أثناء التشغيل.

---

## أماكن حفظ الملفات وتنسيق JSON

### 1) مجلد `Device/` — أجهزة مجمّعة

- الملفات: `devices_001.json`, `devices_002.json`, …
- يستمر ترقيم **`devices_XXX`** تلقائياً اعتماداً على أعلى رقم موجود في المجلد.
- كل ملف يحتوي: `saved_at`, `part`, `devices_per_file`, `count`، ومصفوفة **`devices`**: `{ "batch_index": <int>, "record": { ... } }`.
- **`record`** يشمل عند النجاح حقولاً مثل `status`, `input`, `network`, `device_id`, `install_id`, `register_response`, … **بدون** `request_log` عادة.

### 2) مجلد `generated_devices/` — ملخص الدفعة

- عند كل تشغيل دفعة يُنشأ ملف: **`_batch_summary_YYYYMMDD_HHMMSS.json`**
- يحتوي: `requested_devices`, `threads`, `success`, `failed`, `completed_tasks`, `cancelled`, مسارات المجلدات، حجم الدفعات، و **`network`** (بما فيها **`proxy_url_masked`** إن وُجد بروكسي).

### القيمة الافتراضية لحقل «Output folder»

- تُملأ تلقائياً بمسار **`<مجلد_المشروع>/generated_devices`** (دالة `default_output_dir()`)؛ يمكنك تغيير الحقل ليفتح مجلداً آخر عند **Open output folder** فقط.

---

## البروكسي

- الصيغ المدعومة في الكود: **`http`**, **`https`**, **`socks5`**, **`socks5h`**.
- أمثلة:

  ```text
  http://127.0.0.1:8080
  http://user:password@host:port
  socks5h://127.0.0.1:1080
  ```

- تثبيت **`requests[socks]`** ضروري لاستخدام **SOCKS**.
- في بيانات JSON المُصدَّرة: يُخزَّن **`proxy_url_masked`** (إخفاء كلمة المرور) ضمن **`network`** عند تفعيل البروكسي.

---

## Java والمكتبات الأصلية

- يُستدعى الأمر من مجلد `Libs/` تقريباً بالشكل:

  ```text
  java -Djna.library.path="<prebuilt>" -Djava.library.path="<prebuilt>" -jar unidbg.jar "<message>"
  ```

- **`<prebuilt>`** = `Libs/prebuilt/<نتيجة getsystem()>` مثل `win64` على Windows 64-bit.
- الدالة **`get_java_exe()`** تحاول بالترتيب: **`JAVA_HOME`**, مسار شائع على Windows، ثم **`java`** من `PATH`. على Windows 64-bit تُفضَّل JVM تُبلغ عن **64-Bit** في مخرجات `java -version`.

**معالج Apple Silicon (M1/M2/M3):** حزمة **JNA** داخل **`unidbg.jar`** تتضمن لـ macOS نسخة **x86_64** فقط من `libjnidispatch`. إذا كان **`java`** عندك **arm64** فلن يُحمَّل المكتبة → خطأ **`UnsatisfiedLinkError`** على ملف مؤقت **`jna*.tmp`**. الحل: تثبيت **JDK إنتل / x64** (مثل [Eclipse Temurin macOS x64](https://adoptium.net/))، ضبط **`JAVA_HOME`** عليه، والتحقق أن `java -XshowSettings:properties -version` يعرض **`os.arch = x86_64`**. فحص سريع من جذر المشروع: `python scripts/verify_environment.py`.

---

## استكشاف الأعطال

| العرض | سبب محتمل |
|--------|------------|
| `Missing unidbg.jar` | الملف غير موجود في `Libs/unidbg.jar`. |
| `Missing native libraries` | مجلد `Libs/prebuilt/<منصة>` غير موجود أو لا يطابق جهازك. |
| `UnsatisfiedLinkError` / `Can't load library` … `jna*.tmp` على Mac arm64 | **JVM من نوع arm64** مقابل **JNA x86_64** داخل `unidbg.jar` — ثبّت **JDK x64** ووجّه **`JAVA_HOME`** (راجع قسم Java أعلاه). |
| أخطاء تحميل `libcapstone.dylib` (macOS) | تأكد أن **`libcapstone.dylib`** **رابط رمزي** إلى **`libcapstone.4.dylib`** (ومثلها keystone → **`libkeystone.0.dylib`**). |
| فشل unidbg / لا يظهر `hex=…` | Java غير متوافقة، مسار خاطئ، أو مخرجات غير متوقعة (راجع Log). |
| أخطاء HTTP / JSON | شبكة، حظر، بروكسي خاطئ، أو استجابة غير JSON. |
| بروكسي SOCKS لا يعمل | عدم تثبيت **`requests[socks]`** أو صيغة URL غير مدعومة. |
| أخطاء Tk / أزرار | استخدم Python رسمياً مع Tk مدمج. |

---

## الاعتمادات

- الكود مبني على عمل سابق مُنسب إلى **[xSaleh](https://github.com/xSaleh)** — شكراً للمساهمة الأصلية.
- واجهة العلامة والتطوير الحالية (مثل **Storage TE**) كما هي معرّفة داخل `DeviceGenerator.py`.

---

## المطوّر والشركة والتواصل

| | |
|---|---|
| **المطوّر** | مصطفى الباجوري (Mostafa Al-Bagouri) |
| **الشركة** | **[Storage TE](http://storage-te.com/)** |
| **واتساب** | [+20 100 199 5914](https://wa.me/201001995914) |

---

## دعم المشروع

إن كانت الأداة مفيدة لك، يمكنك — بشكل اختياري — دعم استمرار التطوير والصيانة بأي طريقة تناسبك.

| القناة | الطريقة |
|--------|---------|
| **PayPal** | [paypal.me/sofaapi](https://paypal.me/sofaapi) |
| **Binance Pay / UID** | **1138751298** — إرسال من تطبيق بينانس (Pay / تحويل داخلي عند توفره). |
| **بينانس — إيداع (الويب)** | [إيداع عملة مشفرة (Binance)](https://www.binance.com/ar/my/wallet/account/main/deposit/crypto) — سجّل الدخول، اختر العملة، ثم شبكة **BSC (BEP20)**. |
| **عنوان BSC (للنسخ)** | `0x94c5005229784d9b7df4e7a7a0c3b25a08fd57bc` |

> **الشبكة:** **BSC (BEP-20)** فقط. هذا العنوان لـ **USDT (BEP-20)** و**BTC على BSC** (النسخة المربوطة ببينانس كما في شاشة الإيداع)، وليس لـ **بتكوين الشبكة الأصلية** أو **USDT إيثريوم (ERC-20)** أو **NFT** — لا ترسلها إلى نفس العنوان.

### رموز QR للإيداع (امسح من تطبيق Binance أو أي محفظة تدعم BSC)

| USDT · BSC | BTC · BSC |
|------------|-----------|
| ![رمز إيداع USDT — BSC](assets/deposit-usdt-bsc.png) | ![رمز إيداع BTC على BSC](assets/deposit-btc-bsc.png) |
