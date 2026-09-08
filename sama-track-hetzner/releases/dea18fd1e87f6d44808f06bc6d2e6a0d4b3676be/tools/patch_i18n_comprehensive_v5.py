from pathlib import Path

p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='// SAMA_I18N_COMPREHENSIVE_V5'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

needle="  const originals=new WeakMap();"
if needle not in s:
    raise SystemExit('i18n insertion point not found')

extra=r'''  // SAMA_I18N_COMPREHENSIVE_V5
  const EXTRA={
    en:{
      'Ana Sayfa Gör':'View Dashboard','Sevkiyat Gör':'View Shipments','Sevkiyat / Çıkış / Giriş Düzenle':'Edit Shipment / Exit / Entry','Sevkiyat Sil':'Delete Shipment','Excel / OneDrive İçe Aktar':'Import Excel / OneDrive','Operasyon / Gemi / Yükleme Sırası Gör':'View Operations / Vessel / Loading Queue','Operasyon / Gemi / Yükleme Sırası Düzenle':'Edit Operations / Vessel / Loading Queue','Filo Gör':'View Fleet','Filo Düzenle':'Edit Fleet','Şoförler Gör':'View Drivers','Şoförler Düzenle':'Edit Drivers','Bakım Gör':'View Maintenance','Bakım Düzenle':'Edit Maintenance','Raporlar Gör':'View Reports','Rapor / Excel Dışa Aktar':'Export Report / Excel','İşlem Geçmişi Gör':'View Audit Log','Günlük Kasa Harcama Düzelt':'Edit Daily Cash Expense','Kullanıcılar & Yetkiler Yönet':'Manage Users & Permissions',
      'İlk Admin Hesabını Oluştur':'Create First Admin Account','Ad Soyad':'Full Name','Admin Oluştur':'Create Admin','Giriş Yap':'Sign In','Oturum gerekli.':'Session required.','Şifrenizi değiştirmeden diğer işlemleri kullanamazsınız.':'You must change your password before using other functions.','Bu işlem için yetkiniz yok':'You do not have permission for this action',
      'YÜKLEME & SEVKİYAT':'LOADING & SHIPMENT','FİLO & OPERASYON':'FLEET & OPERATIONS','RAPORLAMA':'REPORTING','SİSTEM':'SYSTEM','YÖNETİM':'MANAGEMENT','OPERASYON MERKEZİ':'OPERATIONS CENTER','FİLO YÖNETİMİ':'FLEET MANAGEMENT','ŞOFÖR YÖNETİMİ':'DRIVER MANAGEMENT','BAKIM YÖNETİMİ':'MAINTENANCE MANAGEMENT',
      'Yeni Çıkış':'New Exit','Yeni Giriş':'New Entry','Çıkış Kaydı':'Exit Record','Giriş Kaydı':'Entry Record','Çıkışı Kaydet':'Save Exit','Girişi Kaydet':'Save Entry','Sevkiyat Bilgileri':'Shipment Information','Çıkış Bilgileri':'Exit Information','Giriş Bilgileri':'Entry Information','Araç ve Şoför':'Vehicle and Driver','Teslimat Bilgileri':'Delivery Information','Yakıt ve Masraflar':'Fuel and Expenses','Mali Bilgiler':'Financial Information','Ekstra Masraflar':'Extra Expenses','Dönüş Bilgileri':'Return Information','Dönüş Harcamaları':'Return Expenses','Müşteri Tahsilatı':'Customer Collection','Şoförün Getirdiği Nakit':'Cash Returned by Driver','Depo Başlangıç Mazot':'Starting Tank Fuel','Depo Bitiş Mazot':'Ending Tank Fuel','Toplam Yakıt':'Total Fuel','Toplam Masraf':'Total Expense','Toplam Tutar':'Total Amount','Toplam Araç':'Total Vehicles','Toplam Şoför':'Total Drivers','Toplam Sevkiyat':'Total Shipments','Toplam Avans':'Total Advances','Toplam Harcama':'Total Expenses','Toplam Kalan':'Total Remaining',
      'GEMİDE ÇALIŞAN':'WORKING ON SHIP','GEMİDE':'ON SHIP','BOŞALTILDI':'UNLOADED','DÖNÜYOR':'RETURNING','BEKLEME':'WAITING','GARAj':'GARAGE','GARJDA':'IN GARAGE','BAKIM':'MAINTENANCE','YOLDA':'ON ROAD','BOŞTA':'AVAILABLE','AKTİF':'ACTIVE','PASİF':'INACTIVE','TAMAMLANDI':'COMPLETED','BEKLİYOR':'WAITING','İPTAL':'CANCELLED',
      'Durum Özeti':'Status Summary','Filo Özeti':'Fleet Summary','Operasyon Özeti':'Operations Summary','Günlük Özet':'Daily Summary','Günlük Yönetici Özeti':'Daily Manager Summary','Aktif Sevkiyatlar':'Active Shipments','Son Sevkiyatlar':'Recent Shipments','Son İşlemler':'Recent Actions','Bekleyen İşler':'Pending Tasks','Uyarılar':'Alerts','Anomaliler':'Anomalies','Performans':'Performance','Yakıt Performansı':'Fuel Performance','Rota Performansı':'Route Performance',
      'Plaka Ara':'Search Plate','Şoför Ara':'Search Driver','SCNA Ara':'Search SCNA','Müşteri Ara':'Search Customer','Bölge Ara':'Search Area','Kayıt Ara':'Search Records','Arama':'Search','Filtre':'Filter','Filtreleri Temizle':'Clear Filters','Sonuçları Göster':'Show Results','Listeyi Yenile':'Refresh List','Listeye Dön':'Back to List','Detayları Gör':'View Details','Detay Göster':'Show Details','Görüntüle':'View','Düzelt':'Correct','Güncelle':'Update','Ekle':'Add','Kaldır':'Remove','Pasife Al':'Deactivate','Aktife Al':'Activate','Geri Al':'Undo','Onayla':'Confirm','Tamamla':'Complete','Başlat':'Start','Bitir':'Finish',
      'Kayıt Tarihi':'Record Date','Oluşturan':'Created By','Güncelleyen':'Updated By','Başlatan':'Started By','Bitiren':'Finished By','Çıkışı Yapan':'Exit Recorded By','Girişi Yapan':'Entry Recorded By','Son İşlem':'Last Action','Son Durum':'Latest Status','Önceki Durum':'Previous Status','Yeni Durum':'New Status','Başlangıç':'Start','Bitiş':'End','Başlangıç Saati':'Start Time','Bitiş Saati':'End Time','Tahmini Çıkış':'Estimated Exit','Tahmini Bitiş':'Estimated Finish','Süre':'Duration','Saat':'Hour','Gün':'Day',
      'Mazot':'Diesel','Yakıt Türü':'Fuel Type','Yakıt Tutarı':'Fuel Amount','Yakıt Litresi':'Fuel Liters','Yakıt Birim Fiyatı':'Fuel Unit Price','Toplam Yakıt Tutarı':'Total Fuel Amount','Resmi':'Official','Ticari':'Commercial','Bağdat':'Baghdad','Depo':'Tank','Başlangıç LT':'Starting Liters','Bitiş LT':'Ending Liters','Alınan LT':'Purchased Liters','Toplam LT':'Total Liters',
      'Şoföre Verilen':'Given to Driver','Şoförden Gelen':'Returned by Driver','Şoför Bakiyesi':'Driver Balance','Müşteri Alacağı':'Customer Receivable','Tahsil Edilen':'Collected','Tahsil Edilecek':'To Be Collected','Kalan Alacak':'Remaining Receivable','Ödenen':'Paid','Ödenecek':'To Be Paid','Bakiye':'Balance','Fark':'Difference','Eksik':'Shortage','Fazla':'Surplus','Eksik Tutar':'Short Amount','Fazla Tutar':'Excess Amount','Nakit':'Cash','Nakit Giriş':'Cash In','Nakit Çıkış':'Cash Out','Fiili Sayım':'Physical Count','Kasa Sayımı':'Cash Count','Kasa Bakiyesi':'Cash Balance','Gün Sonu':'End of Day','Gün Sonu Kasa':'End-of-Day Cash','Açılış Bakiyesi':'Opening Balance','Kapanış Bakiyesi':'Closing Balance',
      'Avans Takibi':'Advance Tracking','Yeni Avans':'New Advance','Avans Ekle':'Add Advance','Avans Alan':'Advance Recipient','Avans Tarihi':'Advance Date','Avans Açıklaması':'Advance Description','Belgelendirilen Harcama':'Documented Expense','Nakit İade / Mahsup':'Cash Return / Offset','Kalan Bakiye':'Remaining Balance','Hesap Kapat':'Close Account','Hesaplaşma Ekle':'Add Settlement','Toplu Fiş/Fatura Girişi':'Bulk Receipt/Invoice Entry','Belge Tarihi':'Document Date','Belge Açıklaması':'Document Description','Makbuz':'Receipt','FİŞ':'RECEIPT','FATURA':'INVOICE','NAKİT İADE':'CASH RETURN','MAHSUP':'OFFSET','USTA':'TECHNICIAN','ŞOFÖR':'DRIVER','PERSONEL':'PERSONNEL','DİĞER':'OTHER',
      'Bakım Geçmişi':'Maintenance History','Bakımda Olan Araçlar':'Vehicles in Maintenance','Bakım Girişi':'Maintenance Entry','Bakım Çıkışı':'Maintenance Exit','Bakım Süresi':'Maintenance Duration','Tahmini Bakım Süresi':'Estimated Maintenance Duration','Bakım Notu':'Maintenance Note','Yapılacak İş':'Work to Do','Yapılan İş':'Work Performed','Bakımı Bitir':'Finish Maintenance','Bakım Kaydını Düzenle':'Edit Maintenance Record',
      'Gemi Adı':'Vessel Name','Yükleme Durumu':'Loading Status','Yük Durumu':'Load Status','Sıra':'Queue','Yükleme Sırasında':'In Loading Queue','Yüklemede':'Loading','Yüklendi':'Loaded','Boş Araç':'Empty Vehicle','Dolu Araç':'Loaded Vehicle','Operasyon Açıklaması':'Operation Description','Operasyon Durumu':'Operation Status',
      'Rota':'Route','Rotalar':'Routes','Rota Standardı':'Route Standard','Beklenen KM':'Expected KM','Beklenen Saat':'Expected Hours','Beklenen Tüketim':'Expected Consumption','Tolerans':'Tolerance','Tüketim':'Consumption','Ortalama':'Average','Ortalama Tüketim':'Average Consumption','Sapma':'Deviation','Risk':'Risk','Yüksek Risk':'High Risk','Normal':'Normal',
      'Veri Kalitesi':'Data Quality','Eksik Veri':'Missing Data','Hatalı Veri':'Invalid Data','Mükerrer':'Duplicate','Mükerrer Kayıt':'Duplicate Record','Kontrol Et':'Check','Kontrol Sonucu':'Check Result','Uygun':'Valid','Uygun Değil':'Invalid','Zorunlu':'Required','Seçim Yapın':'Make a selection','Lütfen bir seçim yapın':'Please make a selection','Lütfen zorunlu alanları doldurun':'Please fill in required fields','İşlem başarılı':'Operation successful','Kayıt başarıyla oluşturuldu':'Record created successfully','Kayıt başarıyla güncellendi':'Record updated successfully','Kayıt silindi':'Record deleted','Bir hata oluştu':'An error occurred','Sunucu hatası':'Server error','Bağlantı hatası':'Connection error','Yetkiniz yok':'Permission denied','Emin misiniz?':'Are you sure?','Bu işlem geri alınamaz':'This action cannot be undone'
    },
    ar:{
      'Ana Sayfa Gör':'عرض الرئيسية','Sevkiyat Gör':'عرض الشحنات','Sevkiyat / Çıkış / Giriş Düzenle':'تعديل الشحنة / الخروج / الدخول','Sevkiyat Sil':'حذف الشحنة','Excel / OneDrive İçe Aktar':'استيراد Excel / OneDrive','Filo Gör':'عرض الأسطول','Filo Düzenle':'تعديل الأسطول','Şoförler Gör':'عرض السائقين','Şoförler Düzenle':'تعديل السائقين','Bakım Gör':'عرض الصيانة','Bakım Düzenle':'تعديل الصيانة','Raporlar Gör':'عرض التقارير','Rapor / Excel Dışa Aktar':'تصدير التقرير / Excel','Kullanıcılar & Yetkiler Yönet':'إدارة المستخدمين والصلاحيات',
      'İlk Admin Hesabını Oluştur':'إنشاء حساب المدير الأول','Ad Soyad':'الاسم الكامل','Admin Oluştur':'إنشاء مدير','Giriş Yap':'تسجيل الدخول','Oturum gerekli.':'الجلسة مطلوبة.','Bu işlem için yetkiniz yok':'ليست لديك صلاحية لهذا الإجراء',
      'YÜKLEME & SEVKİYAT':'التحميل والشحن','FİLO & OPERASYON':'الأسطول والعمليات','RAPORLAMA':'التقارير','SİSTEM':'النظام','YÖNETİM':'الإدارة','OPERASYON MERKEZİ':'مركز العمليات','FİLO YÖNETİMİ':'إدارة الأسطول','ŞOFÖR YÖNETİMİ':'إدارة السائقين','BAKIM YÖNETİMİ':'إدارة الصيانة',
      'Yeni Çıkış':'خروج جديد','Yeni Giriş':'دخول جديد','Çıkış Kaydı':'سجل الخروج','Giriş Kaydı':'سجل الدخول','Çıkışı Kaydet':'حفظ الخروج','Girişi Kaydet':'حفظ الدخول','Sevkiyat Bilgileri':'معلومات الشحنة','Çıkış Bilgileri':'معلومات الخروج','Giriş Bilgileri':'معلومات الدخول','Araç ve Şoför':'المركبة والسائق','Teslimat Bilgileri':'معلومات التسليم','Yakıt ve Masraflar':'الوقود والمصاريف','Mali Bilgiler':'المعلومات المالية','Ekstra Masraflar':'مصاريف إضافية','Dönüş Bilgileri':'معلومات العودة','Dönüş Harcamaları':'مصاريف العودة','Müşteri Tahsilatı':'تحصيل العميل','Şoförün Getirdiği Nakit':'النقد الذي أعاده السائق','Toplam Yakıt':'إجمالي الوقود','Toplam Masraf':'إجمالي المصاريف','Toplam Tutar':'إجمالي المبلغ','Toplam Araç':'إجمالي المركبات','Toplam Şoför':'إجمالي السائقين','Toplam Sevkiyat':'إجمالي الشحنات','Toplam Avans':'إجمالي السلف','Toplam Harcama':'إجمالي المصاريف','Toplam Kalan':'إجمالي المتبقي',
      'GEMİDE ÇALIŞAN':'يعمل على السفينة','GEMİDE':'على السفينة','BOŞALTILDI':'تم التفريغ','DÖNÜYOR':'عائد','BEKLEME':'انتظار','BAKIM':'صيانة','YOLDA':'على الطريق','BOŞTA':'متاح','AKTİF':'نشط','PASİF':'غير نشط','TAMAMLANDI':'مكتمل','BEKLİYOR':'قيد الانتظار','İPTAL':'ملغي',
      'Durum Özeti':'ملخص الحالة','Filo Özeti':'ملخص الأسطول','Operasyon Özeti':'ملخص العمليات','Günlük Özet':'الملخص اليومي','Aktif Sevkiyatlar':'الشحنات النشطة','Son Sevkiyatlar':'أحدث الشحنات','Son İşlemler':'آخر العمليات','Bekleyen İşler':'الأعمال المعلقة','Uyarılar':'التنبيهات','Anomaliler':'الحالات غير الطبيعية','Performans':'الأداء','Yakıt Performansı':'أداء الوقود','Rota Performansı':'أداء المسار',
      'Plaka Ara':'بحث برقم المركبة','Şoför Ara':'بحث عن سائق','SCNA Ara':'بحث SCNA','Müşteri Ara':'بحث عن عميل','Bölge Ara':'بحث عن منطقة','Kayıt Ara':'بحث في السجلات','Arama':'بحث','Filtre':'تصفية','Filtreleri Temizle':'مسح عوامل التصفية','Sonuçları Göster':'عرض النتائج','Listeyi Yenile':'تحديث القائمة','Listeye Dön':'العودة للقائمة','Detayları Gör':'عرض التفاصيل','Görüntüle':'عرض','Düzelt':'تصحيح','Güncelle':'تحديث','Ekle':'إضافة','Kaldır':'إزالة','Pasife Al':'تعطيل','Aktife Al':'تفعيل','Geri Al':'تراجع','Onayla':'تأكيد','Tamamla':'إكمال','Başlat':'بدء','Bitir':'إنهاء',
      'Kayıt Tarihi':'تاريخ السجل','Oluşturan':'أنشأ بواسطة','Güncelleyen':'حدّث بواسطة','Başlatan':'بدأ بواسطة','Bitiren':'أنهى بواسطة','Son İşlem':'آخر إجراء','Son Durum':'آخر حالة','Önceki Durum':'الحالة السابقة','Yeni Durum':'الحالة الجديدة','Başlangıç':'البداية','Bitiş':'النهاية','Süre':'المدة','Saat':'ساعة','Gün':'يوم',
      'Mazot':'ديزل','Yakıt Türü':'نوع الوقود','Yakıt Tutarı':'مبلغ الوقود','Yakıt Litresi':'لترات الوقود','Yakıt Birim Fiyatı':'سعر وحدة الوقود','Toplam Yakıt Tutarı':'إجمالي مبلغ الوقود','Resmi':'رسمي','Ticari':'تجاري','Bağdat':'بغداد','Depo':'الخزان','Başlangıç LT':'لترات البداية','Bitiş LT':'لترات النهاية','Alınan LT':'اللترات المشتراة','Toplam LT':'إجمالي اللترات',
      'Şoföre Verilen':'المعطى للسائق','Şoförden Gelen':'المعاد من السائق','Şoför Bakiyesi':'رصيد السائق','Müşteri Alacağı':'مستحقات العميل','Tahsil Edilen':'المحصّل','Tahsil Edilecek':'المطلوب تحصيله','Kalan Alacak':'المستحق المتبقي','Ödenen':'المدفوع','Ödenecek':'المطلوب دفعه','Bakiye':'الرصيد','Fark':'الفرق','Eksik':'نقص','Fazla':'زيادة','Nakit':'نقد','Nakit Giriş':'دخول نقدي','Nakit Çıkış':'خروج نقدي','Fiili Sayım':'الجرد الفعلي','Kasa Sayımı':'جرد الصندوق','Kasa Bakiyesi':'رصيد الصندوق','Gün Sonu':'نهاية اليوم','Açılış Bakiyesi':'رصيد الافتتاح','Kapanış Bakiyesi':'رصيد الإغلاق',
      'Avans Takibi':'متابعة السلف','Yeni Avans':'سلفة جديدة','Avans Ekle':'إضافة سلفة','Avans Alan':'مستلم السلفة','Avans Tarihi':'تاريخ السلفة','Avans Açıklaması':'وصف السلفة','Belgelendirilen Harcama':'المصروف الموثق','Nakit İade / Mahsup':'إعادة نقد / تسوية','Kalan Bakiye':'الرصيد المتبقي','Hesap Kapat':'إغلاق الحساب','Hesaplaşma Ekle':'إضافة تسوية','Toplu Fiş/Fatura Girişi':'إدخال جماعي للإيصالات/الفواتير','Belge Tarihi':'تاريخ المستند','Belge Açıklaması':'وصف المستند','FİŞ':'إيصال','FATURA':'فاتورة','NAKİT İADE':'إعادة نقد','MAHSUP':'تسوية','USTA':'فني','ŞOFÖR':'سائق','PERSONEL':'موظف','DİĞER':'أخرى',
      'Bakım Geçmişi':'سجل الصيانة','Bakımda Olan Araçlar':'المركبات في الصيانة','Bakım Girişi':'دخول الصيانة','Bakım Çıkışı':'خروج الصيانة','Bakım Süresi':'مدة الصيانة','Tahmini Bakım Süresi':'مدة الصيانة التقديرية','Bakım Notu':'ملاحظة الصيانة','Yapılacak İş':'العمل المطلوب','Yapılan İş':'العمل المنفذ','Bakımı Bitir':'إنهاء الصيانة','Bakım Kaydını Düzenle':'تعديل سجل الصيانة',
      'Gemi Adı':'اسم السفينة','Yükleme Durumu':'حالة التحميل','Yük Durumu':'حالة الحمولة','Sıra':'الدور','Yükleme Sırasında':'في طابور التحميل','Yüklemede':'قيد التحميل','Yüklendi':'تم التحميل','Boş Araç':'مركبة فارغة','Dolu Araç':'مركبة محملة','Operasyon Açıklaması':'وصف العملية','Operasyon Durumu':'حالة العملية',
      'Rota':'المسار','Rotalar':'المسارات','Rota Standardı':'معيار المسار','Beklenen KM':'المسافة المتوقعة','Beklenen Saat':'الساعات المتوقعة','Beklenen Tüketim':'الاستهلاك المتوقع','Tolerans':'السماحية','Tüketim':'الاستهلاك','Ortalama':'المتوسط','Ortalama Tüketim':'متوسط الاستهلاك','Sapma':'الانحراف','Risk':'المخاطر','Yüksek Risk':'مخاطر عالية','Normal':'طبيعي',
      'Veri Kalitesi':'جودة البيانات','Eksik Veri':'بيانات ناقصة','Hatalı Veri':'بيانات خاطئة','Mükerrer':'مكرر','Mükerrer Kayıt':'سجل مكرر','Kontrol Et':'تحقق','Kontrol Sonucu':'نتيجة التحقق','Uygun':'صحيح','Uygun Değil':'غير صحيح','Zorunlu':'إلزامي','Seçim Yapın':'اختر','Lütfen bir seçim yapın':'يرجى الاختيار','Lütfen zorunlu alanları doldurun':'يرجى ملء الحقول المطلوبة','İşlem başarılı':'تمت العملية بنجاح','Kayıt başarıyla oluşturuldu':'تم إنشاء السجل بنجاح','Kayıt başarıyla güncellendi':'تم تحديث السجل بنجاح','Kayıt silindi':'تم حذف السجل','Bir hata oluştu':'حدث خطأ','Sunucu hatası':'خطأ في الخادم','Bağlantı hatası':'خطأ في الاتصال','Yetkiniz yok':'لا توجد صلاحية','Emin misiniz?':'هل أنت متأكد؟','Bu işlem geri alınamaz':'لا يمكن التراجع عن هذا الإجراء'
    }
  };
  Object.assign(DICT.en,EXTRA.en); Object.assign(DICT.ar,EXTRA.ar);
'''
s=s.replace(needle,extra+needle,1)

old="""  function translateString(value,l){
    const raw=value==null?'':String(value), key=raw.trim();
    if(l==='tr'||!key)return raw;
    const translated=DICT[l]&&DICT[l][key];
    return translated?raw.replace(key,translated):raw;
  }"""
new="""  function translateString(value,l){
    const raw=value==null?'':String(value), key=raw.trim();
    if(l==='tr'||!key)return raw;
    const dict=DICT[l]||{};
    if(dict[key]) return raw.replace(key,dict[key]);
    // Translate compound/dynamic UI text too, e.g. \"Toplam Araç: 60\" or \"YOLDA (12)\".
    let out=raw;
    const keys=Object.keys(dict).filter(k=>k.length>=5).sort((a,b)=>b.length-a.length);
    for(const k of keys){
      if(out.includes(k)) out=out.split(k).join(dict[k]);
    }
    return out;
  }"""
if old not in s:
    raise SystemExit('translateString block not found')
s=s.replace(old,new,1)

old2="document.querySelectorAll('input,textarea,button,[title]').forEach(el=>translateAttrs(el,l));"
new2="document.querySelectorAll('input,textarea,button,select,option,[title],[aria-label],[data-label]').forEach(el=>translateAttrs(el,l));"
if old2 in s:
    s=s.replace(old2,new2,1)

old3="for(const a of ['placeholder','title']){"
new3="for(const a of ['placeholder','title','aria-label','data-label']){"
if old3 in s:
    s=s.replace(old3,new3,1)

hook="  window.setSamaLanguage=applyLanguage;"
wrap=r'''  const _samaAlert=window.alert.bind(window), _samaConfirm=window.confirm.bind(window), _samaPrompt=window.prompt.bind(window);
  window.alert=(m)=>_samaAlert(translateString(m,lang()));
  window.confirm=(m)=>_samaConfirm(translateString(m,lang()));
  window.prompt=(m,d)=>_samaPrompt(translateString(m,lang()),d);
'''
if hook in s and wrap.strip() not in s:
    s=s.replace(hook,wrap+hook,1)

p.write_text(s,encoding='utf-8')
print('patched')
