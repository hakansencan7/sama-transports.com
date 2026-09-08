# Final local-only UI language layer for SAMA TRACK.
#
# The base app already has a TR/EN/AR translation engine, language selector,
# localStorage persistence and MutationObserver. Newer patch modules added UI
# strings after that dictionary was written. This module extends the SAME engine
# instead of adding a second observer/translator, so dynamically rendered panels,
# modals and alerts keep one authoritative language state.

import kolaybi_purchase_product_workflow_patch as base

app = base.app
core = base.core
html = core.HTML

MARK = "// SAMA_I18N_FINAL_RUNTIME_V1"
ANCHOR = "  const originals=new WeakMap();"

if MARK not in html:
    if ANCHOR not in html:
        raise RuntimeError("SAMA i18n engine anchor not found; final language layer not installed")

    block = r'''  // SAMA_I18N_FINAL_RUNTIME_V1
  // English/mixed labels introduced by later runtime patches also need a real
  // Turkish representation. Therefore TR is a dictionary too, not merely the
  // untouched source language.
  const FINAL_I18N={
    tr:{
      'SATIN ALMA / PURCHASE':'SATIN ALMA','SATIŞ / SALE':'SATIŞ','PURCHASE':'SATIN ALMA','SALE':'SATIŞ',
      'PURCHASE TOTAL':'SATIN ALMA TOPLAMI','TOTAL PURCHASE':'TOPLAM SATIN ALMA','SALE TOTAL':'SATIŞ TOPLAMI',
      'PURCHASE CARİ':'SATIN ALMA CARİSİ','SALE MÜŞTERİ':'SATIŞ MÜŞTERİSİ','SALE ÜRÜN':'SATIŞ ÜRÜNÜ',
      'GİDER / PRODUCT':'GİDER / ÜRÜN','PRODUCT':'ÜRÜN','PRODUCT ID':'ÜRÜN ID','QTY':'ADET / MİKTAR',
      'UNIT PRICE':'BİRİM FİYAT','TOTAL':'TOPLAM','PLATE':'PLAKA','DRIVER':'ŞOFÖR','CUSTOMER':'MÜŞTERİ',
      'ROUTE':'ROTA','DATE':'TARİH','SOURCE':'KAYNAK','Contact ID':'Cari ID','Address ID':'Adres ID',
      'WAITING':'BEKLEME','OTHER':'DİĞER','PORT FEE':'LİMAN ÜCRETİ','DOCK FEE':'YÜKLEME / RIHTIM ÜCRETİ',
      'OFFICIAL FUEL':'RESMİ MAZOT','COMMERCIAL FUEL':'TİCARİ MAZOT','ROAD FUEL':'YOL MAZOTU',
      'PREMIUM':'PRİM','ALLOWANCE':'HARCIRAH','FREIGHT':'NAVLUN','COLLECTION':'TAHSİLAT',
      'READY':'HAZIR','MISSING':'EKSİK','SENT':'GÖNDERİLDİ','SELECTED':'SEÇİLDİ',
      'LOCAL DB':'YEREL DB','KOLAYBI LIVE':'KOLAYBI CANLI','SELECTED FOR PURCHASE':'SATIN ALMA İÇİN SEÇİLDİ',
      'CREATED FROM SAMA PURCHASE':'SAMA SATIN ALMADAN OLUŞTURULDU',
      'TEK SCNA İŞLEM':'TEK SCNA İŞLEM','AYARLAR / EŞLEŞTİRMELER':'AYARLAR / EŞLEŞTİRMELER',
      'SCNA KONTROLÜNÜ GETİR':'SCNA KONTROLÜNÜ GETİR','SCNA HAZIRLANIYOR...':'SCNA HAZIRLANIYOR...',
      'SCNA HAZIRLANDI':'SCNA HAZIRLANDI','SATIN ALMA FATURASI GÖNDER':'SATIN ALMA FATURASI GÖNDER',
      'SATIŞ FATURASI GÖNDER':'SATIŞ FATURASI GÖNDER','ÜRÜN ARA / EŞLEŞTİR':'ÜRÜN ARA / EŞLEŞTİR',
      'YENİ ÜRÜN OLUŞTUR':'YENİ ÜRÜN OLUŞTUR','DB + KOLAYBI ARA':'DB + KOLAYBI ARA',
      'MEVCUT ÜRÜNÜ SEÇ':'MEVCUT ÜRÜNÜ SEÇ','SEÇİLEN ÜRÜNÜ EŞLEŞTİR':'SEÇİLEN ÜRÜNÜ EŞLEŞTİR',
      "KOLAYBI'DE ÜRÜN OLUŞTUR":"KOLAYBI'DE ÜRÜN OLUŞTUR",'EKSİK PURCHASE ÜRÜNÜNÜ ÇÖZ':'EKSİK SATIN ALMA ÜRÜNÜNÜ ÇÖZ',
      'PURCHASE ÜRÜN ÇÖZÜMLEYİCİ':'SATIN ALMA ÜRÜN ÇÖZÜMLEYİCİ','ÜRÜN ADI / KODU ARA':'ÜRÜN ADI / KODU ARA',
      'ÜRÜN ADI':'ÜRÜN ADI','ÜRÜN KODU':'ÜRÜN KODU','KDV %':'KDV %',
      'SALE ÜRÜN EŞLEŞTİ':'SATIŞ ÜRÜNÜ EŞLEŞTİ','SALE ÜRÜN BUL / EŞLEŞTİR':'SATIŞ ÜRÜNÜ BUL / EŞLEŞTİR',
      'SATIŞ ÜRÜNÜ BULUNAMADI / EŞLEŞMEDİ':'SATIŞ ÜRÜNÜ BULUNAMADI / EŞLEŞMEDİ',
      'DEĞİŞTİR / KONTROL ET':'DEĞİŞTİR / KONTROL ET','SERIAL DB YENİLE':'SERİ DB YENİLE',
      'PURCHASE + SALE':'SATIN ALMA + SATIŞ','INVOICE':'FATURA','GENERAL EXPENSE':'GENEL GİDER',
      'Document ID':'Belge ID','Serial':'Seri','Description':'Açıklama','Tax Office':'Vergi Dairesi',
      'RETURN EXPENSES':'DÖNÜŞ MASRAFLARI','TOTAL RETURN EXPENSES':'TOPLAM DÖNÜŞ MASRAFLARI',
      'RETURN EXTRA EXPENSES':'DÖNÜŞ EK MASRAFLARI','TOTAL EXPENSES':'TOPLAM MASRAFLAR',
      'DRIVER SHOULD HAND OVER':'ŞOFÖRÜN TESLİM ETMESİ GEREKEN',
      'EXIT EXPENSES TOTAL':'ÇIKIŞ MASRAFLARI TOPLAMI','DIESEL IN TANK':'DEPODAKİ MAZOT',
      'WEIGHT (KG)':'AĞIRLIK (KG)','TOTAL FREIGHT':'TOPLAM NAVLUN',
      'BEKLEME / WAITING':'BEKLEME','DİĞER / OTHER':'DİĞER','PORT FEE / PORT FEE':'LİMAN ÜCRETİ',
      'BASRA MAZOT RESMİ / BASRA OFFICIAL FUEL':'BASRA RESMİ MAZOT',
      'Finans / Kârlılık Gör':'Finans / Kârlılık Gör','Avans / Kişi Hesapları Gör':'Avans / Kişi Hesapları Gör',
      'Avans / Kişi Hesapları Ekle-Düzenle':'Avans / Kişi Hesapları Ekle-Düzenle',
      'Günlük Kasa Gör':'Günlük Kasa Gör','Günlük Kasa Ekle-Düzenle':'Günlük Kasa Ekle-Düzenle',
      'KolayBi Gör':'KolayBi Gör','KolayBi Ayar / Eşleştirme Düzenle':'KolayBi Ayar / Eşleştirme Düzenle',
      'KolayBi Fatura Gönder':'KolayBi Fatura Gönder'
    },
    en:{
      'SATIN ALMA / PURCHASE':'PURCHASE','SATIŞ / SALE':'SALE','SATIN ALMA':'Purchase','SATIŞ':'Sale',
      'PURCHASE CARİ':'PURCHASE ACCOUNT','SALE MÜŞTERİ':'SALE CUSTOMER','SALE ÜRÜN':'SALE PRODUCT',
      'GİDER / PRODUCT':'EXPENSE / PRODUCT','Kaynak':'Source','Eşleşme':'Match','Cari':'Account',
      'Cari ID':'Account ID','Adres ID':'Address ID','Belge ID':'Document ID','Seri':'Serial',
      'TEK SCNA İŞLEM':'SINGLE SCNA TRANSACTION','AYARLAR / EŞLEŞTİRMELER':'SETTINGS / MAPPINGS',
      'SCNA KONTROLÜNÜ GETİR':'LOAD SCNA CHECK','SCNA HAZIRLANIYOR...':'PREPARING SCNA...',
      'SCNA HAZIRLANDI':'SCNA READY','SATIN ALMA FATURASI GÖNDER':'SEND PURCHASE INVOICE',
      'SATIŞ FATURASI GÖNDER':'SEND SALE INVOICE','ÜRÜN ARA / EŞLEŞTİR':'SEARCH / MAP PRODUCT',
      'YENİ ÜRÜN OLUŞTUR':'CREATE NEW PRODUCT','DB + KOLAYBI ARA':'SEARCH DB + KOLAYBI',
      'MEVCUT ÜRÜNÜ SEÇ':'SELECT EXISTING PRODUCT','SEÇİLEN ÜRÜNÜ EŞLEŞTİR':'MAP SELECTED PRODUCT',
      "KOLAYBI'DE ÜRÜN OLUŞTUR":'CREATE PRODUCT IN KOLAYBI','EKSİK PURCHASE ÜRÜNÜNÜ ÇÖZ':'RESOLVE MISSING PURCHASE PRODUCT',
      'PURCHASE ÜRÜN ÇÖZÜMLEYİCİ':'PURCHASE PRODUCT RESOLVER','ÜRÜN ADI / KODU ARA':'SEARCH PRODUCT NAME / CODE',
      'ÜRÜN ADI':'PRODUCT NAME','ÜRÜN KODU':'PRODUCT CODE','KDV %':'VAT %',
      'Önce mevcut KolayBi ürününü ara/eşleştir. Gerçekten yoksa yeni ürün oluştur.':'Search/map the existing KolayBi product first. Create a new product only if it truly does not exist.',
      'Yeni ürün ancak onaydan sonra gerçek KolayBi hesabında oluşturulur.':'A new product is created in the real KolayBi account only after confirmation.',
      'Product ID eksik':'Product ID missing','SALE ÜRÜN EŞLEŞTİ':'SALE PRODUCT MAPPED',
      'SALE ÜRÜN BUL / EŞLEŞTİR':'FIND / MAP SALE PRODUCT','DEĞİŞTİR / KONTROL ET':'CHANGE / CHECK',
      'SATIŞ ÜRÜNÜ BULUNAMADI / EŞLEŞMEDİ':'SALE PRODUCT NOT FOUND / NOT MAPPED',
      'Satış faturası gönderimi durduruldu. Önce KolayBi\'de mevcut ürünü ara ve eşleştir. Gerçekten yoksa yeni ürünü buradan oluştur.':'Sale invoice sending is blocked. Search and map an existing KolayBi product first; create one here only if it truly does not exist.',
      'Bölge / ürün adı':'Area / product name','MEVCUT ÜRÜNÜ SEÇ':'SELECT EXISTING PRODUCT',
      'ÜRÜNLERİ ÇEK':'SYNC PRODUCTS','SABİT ÜRÜNLERİ EŞLEŞTİR':'MAP FIXED PRODUCTS',
      'SERIAL DB YENİLE':'REFRESH SERIAL DB','SERİ DB YENİLE':'REFRESH SERIAL DB',
      'PURCHASE + SALE serial listesi':'PURCHASE + SALE serial list','SATIN ALMA / INVOICE':'PURCHASE / INVOICE',
      'GENEL GİDER':'GENERAL EXPENSE','MUHASEBE KONTROL':'ACCOUNTING CHECK','BELGE NO':'DOCUMENT NO',
      'RETURN EXPENSES (FUEL + EXTRA)':'RETURN EXPENSES (FUEL + EXTRA)',
      'TOTAL RETURN EXPENSES':'TOTAL RETURN EXPENSES','RETURN EXTRA EXPENSES':'RETURN EXTRA EXPENSES',
      'TOPLAM DÖNÜŞ MASRAFLARI':'TOTAL RETURN EXPENSES','DÖNÜŞ EK MASRAFLARI':'RETURN EXTRA EXPENSES',
      'ŞOFÖRÜN TESLİM ETMESİ GEREKEN':'DRIVER SHOULD HAND OVER','TOPLAM MASRAFLAR':'TOTAL EXPENSES',
      'BEKLEME / WAITING':'WAITING','DİĞER / OTHER':'OTHER','BASRA MAZOT RESMİ / BASRA OFFICIAL FUEL':'BASRA OFFICIAL FUEL',
      'Finans / Kârlılık Gör':'View Finance / Profitability','Avans / Kişi Hesapları Gör':'View Advances / Person Accounts',
      'Avans / Kişi Hesapları Ekle-Düzenle':'Add/Edit Advances / Person Accounts','Günlük Kasa Gör':'View Daily Cash',
      'Günlük Kasa Ekle-Düzenle':'Add/Edit Daily Cash','KolayBi Gör':'View KolayBi',
      'KolayBi Ayar / Eşleştirme Düzenle':'Edit KolayBi Settings / Mappings','KolayBi Fatura Gönder':'Send KolayBi Invoice',
      'Ekle-Düzenle':'Add/Edit','Gör':'View','Eşleştirme':'Mapping','Gönder':'Send','Yenile':'Refresh','Çöz':'Resolve'
    },
    ar:{
      'SATIN ALMA / PURCHASE':'الشراء','SATIŞ / SALE':'البيع','SATIN ALMA':'الشراء','SATIŞ':'البيع',
      'PURCHASE':'الشراء','SALE':'البيع','PURCHASE TOTAL':'إجمالي الشراء','SALE TOTAL':'إجمالي البيع',
      'PURCHASE CARİ':'حساب الشراء','SALE MÜŞTERİ':'عميل البيع','SALE ÜRÜN':'منتج البيع',
      'GİDER / PRODUCT':'المصروف / المنتج','PRODUCT':'المنتج','PRODUCT ID':'معرف المنتج','QTY':'الكمية',
      'UNIT PRICE':'سعر الوحدة','TOTAL':'الإجمالي','PLATE':'رقم اللوحة','DRIVER':'السائق','CUSTOMER':'العميل',
      'ROUTE':'المسار','DATE':'التاريخ','SOURCE':'المصدر','Kaynak':'المصدر','Eşleşme':'المطابقة',
      'Contact ID':'معرف الحساب','Address ID':'معرف العنوان','Cari ID':'معرف الحساب','Adres ID':'معرف العنوان',
      'Document ID':'معرف المستند','Belge ID':'معرف المستند','Serial':'الرقم التسلسلي','Seri':'الرقم التسلسلي',
      'WAITING':'انتظار','OTHER':'أخرى','PORT FEE':'رسوم الميناء','DOCK FEE':'رسوم الرصيف / التحميل',
      'OFFICIAL FUEL':'وقود رسمي','COMMERCIAL FUEL':'وقود تجاري','ROAD FUEL':'وقود الطريق',
      'PREMIUM':'حافز','ALLOWANCE':'مخصصات','FREIGHT':'أجرة النقل','COLLECTION':'التحصيل',
      'READY':'جاهز','MISSING':'ناقص','SENT':'تم الإرسال','SELECTED':'تم الاختيار',
      'LOCAL DB':'قاعدة البيانات المحلية','KOLAYBI LIVE':'KolayBi مباشر',
      'TEK SCNA İŞLEM':'معاملة SCNA واحدة','AYARLAR / EŞLEŞTİRMELER':'الإعدادات / المطابقات',
      'SCNA KONTROLÜNÜ GETİR':'جلب فحص SCNA','SCNA HAZIRLANIYOR...':'جارٍ تجهيز SCNA...',
      'SCNA HAZIRLANDI':'SCNA جاهز','SATIN ALMA FATURASI GÖNDER':'إرسال فاتورة الشراء',
      'SATIŞ FATURASI GÖNDER':'إرسال فاتورة البيع','ÜRÜN ARA / EŞLEŞTİR':'بحث / مطابقة المنتج',
      'YENİ ÜRÜN OLUŞTUR':'إنشاء منتج جديد','DB + KOLAYBI ARA':'بحث في قاعدة البيانات + KolayBi',
      'MEVCUT ÜRÜNÜ SEÇ':'اختيار منتج موجود','SEÇİLEN ÜRÜNÜ EŞLEŞTİR':'مطابقة المنتج المحدد',
      "KOLAYBI'DE ÜRÜN OLUŞTUR":'إنشاء المنتج في KolayBi','EKSİK PURCHASE ÜRÜNÜNÜ ÇÖZ':'حل منتج الشراء الناقص',
      'PURCHASE ÜRÜN ÇÖZÜMLEYİCİ':'معالج منتج الشراء','ÜRÜN ADI / KODU ARA':'بحث باسم / رمز المنتج',
      'ÜRÜN ADI':'اسم المنتج','ÜRÜN KODU':'رمز المنتج','KDV %':'ضريبة القيمة المضافة %',
      'Önce mevcut KolayBi ürününü ara/eşleştir. Gerçekten yoksa yeni ürün oluştur.':'ابحث أولاً عن منتج KolayBi الموجود وطابقه. أنشئ منتجاً جديداً فقط إذا لم يكن موجوداً فعلاً.',
      'Yeni ürün ancak onaydan sonra gerçek KolayBi hesabında oluşturulur.':'يتم إنشاء المنتج الجديد في حساب KolayBi الحقيقي فقط بعد التأكيد.',
      'Product ID eksik':'معرف المنتج ناقص','SALE ÜRÜN EŞLEŞTİ':'تمت مطابقة منتج البيع',
      'SALE ÜRÜN BUL / EŞLEŞTİR':'بحث / مطابقة منتج البيع','DEĞİŞTİR / KONTROL ET':'تغيير / تحقق',
      'SATIŞ ÜRÜNÜ BULUNAMADI / EŞLEŞMEDİ':'منتج البيع غير موجود / غير مطابق',
      'Satış faturası gönderimi durduruldu. Önce KolayBi\'de mevcut ürünü ara ve eşleştir. Gerçekten yoksa yeni ürünü buradan oluştur.':'تم إيقاف إرسال فاتورة البيع. ابحث أولاً عن منتج موجود في KolayBi وطابقه، وأنشئ منتجاً جديداً هنا فقط إذا لم يكن موجوداً فعلاً.',
      'Bölge / ürün adı':'المنطقة / اسم المنتج','ÜRÜNLERİ ÇEK':'مزامنة المنتجات',
      'SABİT ÜRÜNLERİ EŞLEŞTİR':'مطابقة المنتجات الثابتة','SERIAL DB YENİLE':'تحديث قاعدة الأرقام التسلسلية',
      'SERİ DB YENİLE':'تحديث قاعدة الأرقام التسلسلية','PURCHASE + SALE serial listesi':'قائمة أرقام الشراء + البيع',
      'SATIN ALMA / INVOICE':'الشراء / الفاتورة','INVOICE':'فاتورة','GENERAL EXPENSE':'مصروف عام','GENEL GİDER':'مصروف عام',
      'MUHASEBE KONTROL':'تدقيق المحاسبة','BELGE NO':'رقم المستند','Description':'الوصف','Tax Office':'دائرة الضريبة',
      'RETURN EXPENSES (FUEL + EXTRA)':'مصاريف العودة (الوقود + الإضافية)','RETURN EXPENSES':'مصاريف العودة',
      'TOTAL RETURN EXPENSES':'إجمالي مصاريف العودة','RETURN EXTRA EXPENSES':'مصاريف العودة الإضافية',
      'TOTAL EXPENSES':'إجمالي المصاريف','DRIVER SHOULD HAND OVER':'المبلغ الذي يجب على السائق تسليمه',
      'EXIT EXPENSES TOTAL':'إجمالي مصاريف الخروج','DIESEL IN TANK':'الوقود في الخزان',
      'WEIGHT (KG)':'الوزن (كغم)','TOTAL FREIGHT':'إجمالي أجرة النقل',
      'BEKLEME / WAITING':'انتظار','DİĞER / OTHER':'أخرى','PORT FEE / PORT FEE':'رسوم الميناء',
      'BASRA MAZOT RESMİ / BASRA OFFICIAL FUEL':'وقود البصرة الرسمي',
      'Finans / Kârlılık Gör':'عرض المالية / الربحية','Avans / Kişi Hesapları Gör':'عرض السلف / حسابات الأشخاص',
      'Avans / Kişi Hesapları Ekle-Düzenle':'إضافة/تعديل السلف / حسابات الأشخاص','Günlük Kasa Gör':'عرض الصندوق اليومي',
      'Günlük Kasa Ekle-Düzenle':'إضافة/تعديل الصندوق اليومي','KolayBi Gör':'عرض KolayBi',
      'KolayBi Ayar / Eşleştirme Düzenle':'تعديل إعدادات / مطابقات KolayBi','KolayBi Fatura Gönder':'إرسال فاتورة KolayBi',
      'Ekle-Düzenle':'إضافة/تعديل','Gör':'عرض','Eşleştirme':'مطابقة','Gönder':'إرسال','Yenile':'تحديث','Çöz':'حل',
      'Cari':'الحساب','Vergi Dairesi':'دائرة الضريبة','Fatura Gönder':'إرسال فاتورة','Kişi Hesapları':'حسابات الأشخاص'
    }
  };
  for(const l of ['tr','en','ar']) DICT[l]=Object.assign(DICT[l]||{},FINAL_I18N[l]||{});

  // Word fallback is intentionally conservative. Exact/long phrase matches above
  // win first; these tokens only rescue newly introduced short labels.
  const FINAL_WORDS={
    tr:{'PURCHASE':'SATIN ALMA','SALE':'SATIŞ','PRODUCT':'ÜRÜN','TOTAL':'TOPLAM','QTY':'MİKTAR','DRIVER':'ŞOFÖR','CUSTOMER':'MÜŞTERİ','ROUTE':'ROTA','DATE':'TARİH','PLATE':'PLAKA','WAITING':'BEKLEME','OTHER':'DİĞER','READY':'HAZIR','MISSING':'EKSİK','SENT':'GÖNDERİLDİ','SOURCE':'KAYNAK','INVOICE':'FATURA','Description':'Açıklama'},
    en:{'Eşleştir':'Map','Eşleştirme':'Mapping','Oluştur':'Create','Gönder':'Send','Yenile':'Refresh','Çöz':'Resolve','Cari':'Account','Ürün':'Product','Vergi':'Tax','Dairesi':'Office','Seri':'Serial','Belge':'Document','Satın':'Purchase','Satış':'Sale','Hazır':'Ready','Gönderildi':'Sent','Eksik':'Missing','Kaynak':'Source','Adres':'Address','Hesapları':'Accounts','Gör':'View'},
    ar:{'PURCHASE':'الشراء','SALE':'البيع','PRODUCT':'المنتج','TOTAL':'الإجمالي','QTY':'الكمية','DRIVER':'السائق','CUSTOMER':'العميل','ROUTE':'المسار','DATE':'التاريخ','PLATE':'رقم اللوحة','WAITING':'انتظار','OTHER':'أخرى','READY':'جاهز','MISSING':'ناقص','SENT':'تم الإرسال','SOURCE':'المصدر','INVOICE':'فاتورة','Eşleştir':'مطابقة','Eşleştirme':'مطابقة','Oluştur':'إنشاء','Gönder':'إرسال','Yenile':'تحديث','Çöz':'حل','Cari':'الحساب','Ürün':'المنتج','Vergi':'الضريبة','Dairesi':'الدائرة','Seri':'تسلسلي','Belge':'مستند','Satın':'شراء','Satış':'بيع','Hazır':'جاهز','Gönderildi':'تم الإرسال','Eksik':'ناقص','Kaynak':'المصدر','Adres':'العنوان','Hesapları':'الحسابات','Gör':'عرض'}
  };
  for(const l of ['tr','en','ar']) WORD7B[l]=Object.assign(WORD7B[l]||{},FINAL_WORDS[l]||{});
'''

    html = html.replace(ANCHOR, block + ANCHOR, 1)

    # The older engine treated Turkish as "do nothing". That left English labels
    # introduced by later patches untranslated in TR mode. DICT.tr now handles them.
    old_guard = "if(l==='tr'||!key)return raw;"
    if old_guard not in html:
        raise RuntimeError("SAMA i18n Turkish guard not found")
    html = html.replace(old_guard, "if(!key)return raw;", 1)

    # Arabic keeps RTL at document level, while identifiers/numbers stay readable.
    rtl_css = r'''<style id="samaFinalI18nRtl">
html[dir="rtl"] input,html[dir="rtl"] textarea,html[dir="rtl"] select{direction:rtl;text-align:right}
html[dir="rtl"] input[type="number"],html[dir="rtl"] input[type="date"],html[dir="rtl"] input[type="time"],html[dir="rtl"] .mono{direction:ltr;text-align:left}
html[dir="rtl"] #samaLangBox{direction:ltr}
</style>'''
    if '</head>' in html and 'id="samaFinalI18nRtl"' not in html:
        html = html.replace('</head>', rtl_css + '</head>', 1)

    core.HTML = html
    print('[SAMA] Final local TR/EN/AR language layer active')
