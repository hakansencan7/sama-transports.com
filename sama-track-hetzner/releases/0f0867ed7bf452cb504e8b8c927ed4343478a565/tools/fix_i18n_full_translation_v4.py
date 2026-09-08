from pathlib import Path
import re

p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='// SAMA_I18N_FULL_TRANSLATION_V4'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

start=s.find('const DICT={')
end=s.find('  const originals=', start)
if start<0 or end<0:
    raise SystemExit('i18n dictionary block not found')

block=r'''const DICT={
 en:{
  'Ana Sayfa':'Dashboard','Çıkış İşlemleri':'Exit Operations','Giriş İşlemleri':'Entry Operations','Operasyon':'Operations','Filo':'Fleet','Şoförler':'Drivers','Bakım':'Maintenance','Raporlar':'Reports','Ayarlar':'Settings','Muhasebe & Finans':'Accounting & Finance','MUHASEBE & FİNANS':'ACCOUNTING & FINANCE','Günlük Kasa':'Daily Cash','Avans Takip':'Advance Tracking','Kullanıcılar & Yetkiler':'Users & Permissions','Kullanıcı Adı':'Username','Şifre':'Password','Giriş':'Login','Çıkış':'Logout','Kaydet':'Save','İptal':'Cancel','Kapat':'Close','Düzenle':'Edit','Sil':'Delete','Yeni Kayıt':'New Record','Ara':'Search','Tarih':'Date','Plaka':'Plate','Şoför':'Driver','Tutar':'Amount','Açıklama':'Description','Durum':'Status','Beklemede':'Waiting','Bakımda':'Maintenance','Yolda':'On Road','Boşta':'Available','Gemide Çalışan':'Working on Ship','Boşaltıldı Dönüyor':'Unloaded / Returning','Toplam':'Total','Para Birimi':'Currency','Yetkiler':'Permissions','Kullanıcılar':'Users',
  'Sevkiyat':'Shipment','Sevkiyatlar':'Shipments','Yeni Sevkiyat':'New Shipment','Yeni Sevkiyat Ekle':'Add New Shipment','Çıkış':'Exit','Giriş':'Entry','Çıkış Tarihi':'Exit Date','Giriş Tarihi':'Entry Date','Çıkış Saati':'Exit Time','Giriş Saati':'Entry Time','Çıkış KM':'Exit KM','Giriş KM':'Entry KM','Müşteri':'Customer','Bölge':'Area','Teslimat Bölgesi':'Delivery Area','Mal Tipi':'Cargo Type','Net KG':'Net KG','Navlun':'Freight','Navlun Birim Fiyat':'Freight Unit Price','Harcırah':'Allowance','Prim':'Premium','Diğer':'Other','Not':'Note','Telefon':'Phone','D.No':'D.No','Depo Mazot':'Tank Fuel','Resmi Mazot':'Official Fuel','Ticari Mazot':'Commercial Fuel','Bağdat Mazot':'Baghdad Fuel','Litre':'Liter','Birim Fiyat':'Unit Price','Yakıt':'Fuel','Yakıt Alımı':'Fuel Purchase','Port Fee':'Port Fee','Dock Fee':'Dock Fee','SONAR':'SONAR','Tahsilat':'Collection','Kalan':'Remaining','Getirilen Para':'Cash Returned','Şoförün Getirdiği Para':'Cash Returned by Driver','Şoförün Vermesi Gereken Para':'Cash Driver Must Return','Şoföre Verilmesi Gereken':'Cash to Give Driver','Çıkış Parası':'Exit Cash','Çıkış Parası Eksik':'Missing Exit Cash',
  'Aktif':'Active','Pasif':'Inactive','Tamamlandı':'Completed','Bekliyor':'Waiting','Çıkışta':'Outbound','Girişte':'Inbound','TAMAMLANDI':'COMPLETED','ÇIKIŞTA':'OUTBOUND','GİRİŞTE':'INBOUND','GEMİDE ÇALIŞIYOR':'WORKING ON SHIP','BAKIMDA':'IN MAINTENANCE','YOLDA':'ON ROAD','BOŞALTILDI DÖNÜYOR':'UNLOADED / RETURNING','BEKLEMEDE':'WAITING','BOŞTA':'AVAILABLE',
  'Araç':'Vehicle','Araçlar':'Vehicles','Araç Ekle':'Add Vehicle','Araç Düzenle':'Edit Vehicle','Marka':'Brand','Model':'Model','Araç Tipi':'Vehicle Type','Garaj Durumu':'Garage Status','Gemi':'Vessel','Gemi Operasyonu':'Vessel Operation','Yükleme Sırası':'Loading Queue','Sıra No':'Queue No','Operasyon Notu':'Operation Note','Filo Durumu':'Fleet Status','Araç Durumu':'Vehicle Status','GPS Durumu':'GPS Status','Son Güncelleme':'Last Update',
  'Şoför Ekle':'Add Driver','Şoför Düzenle':'Edit Driver','Şoför No':'Driver No','Şoför Adı':'Driver Name','Telefon No':'Phone Number','Aktif Şoförler':'Active Drivers','Pasif Şoförler':'Inactive Drivers',
  'Bakım Kaydı':'Maintenance Record','Aracı Bakıma Al':'Send Vehicle to Maintenance','Bakım Bitti':'Maintenance Finished','Bakım Başlangıç':'Maintenance Start','Bakım Bitiş':'Maintenance End','Bakım Nedeni':'Maintenance Reason','Bakım Açıklaması':'Maintenance Description','Yapılan İşlem':'Work Performed','Tahmini Süre':'Estimated Duration','Önceki Durum':'Previous Status','DÜZENLE':'EDIT',
  'Rapor':'Report','Raporlar':'Reports','Filtrele':'Filter','Temizle':'Clear','Dışa Aktar':'Export','Excel Dışa Aktar':'Export Excel','Excel İçe Aktar':'Import Excel','İçe Aktar':'Import','Başlangıç Tarihi':'Start Date','Bitiş Tarihi':'End Date','Tarih Aralığı':'Date Range','Tümü':'All','Sonuç':'Result','Kayıt':'Record','Kayıtlar':'Records','Kayıt Sayısı':'Record Count','Toplam Kayıt':'Total Records',
  'Gün Başı':'Opening Cash','Sevkiyattan Gelen':'Cash from Shipments','Diğer Kasa Girişi':'Other Cash In','Diğer Giriş':'Other Inflow','Sevkiyat Çıkışı / Şoföre Verilen':'Shipment Outflow / Given to Driver','Avans':'Advance','Avanslar':'Advances','Doğrudan Harcama':'Direct Expense','Harcama':'Expense','Harcamalar':'Expenses','Beklenen Kasa':'Expected Cash','Beklenen':'Expected','Fiili Kasa':'Physical Cash','Fiili':'Physical','Açık':'Difference','Kasa':'Cash','Kasa Girişi':'Cash In','Kasa Çıkışı':'Cash Out','Belge No':'Document No','Fatura No':'Invoice No','Fiş No':'Receipt No','Fatura':'Invoice','Fiş':'Receipt','Nakit İade':'Cash Return','Mahsup':'Offset','Belge Türü':'Document Type','Hesaplaşma':'Settlement','Hesaplaşmalar':'Settlements','Kalan Avans':'Remaining Advance','Avans Tutarı':'Advance Amount','Avans Ver':'Give Advance','Avans Düzenle':'Edit Advance','Kişi':'Person','Kişi Tipi':'Person Type','Usta':'Technician','Personel':'Personnel','Diğer':'Other',
  'Kullanıcı':'User','Rol':'Role','Yetki':'Permission','Yetkiler':'Permissions','Kullanıcı Ekle':'Add User','Kullanıcı Düzenle':'Edit User','Şifre Değiştir':'Change Password','Yeni Şifre':'New Password','Mevcut Şifre':'Current Password','Çıkış Yap':'Logout','Oturum':'Session','Admin':'Admin','Operatör':'Operator','İzleyici':'Viewer',
  'İşlem Geçmişi':'Audit Log','İşlem':'Action','Oluşturulma Tarihi':'Created Date','Güncelleme Tarihi':'Updated Date','Detay':'Detail','Silindi':'Deleted','Güncellendi':'Updated','Eklendi':'Added','Başarılı':'Successful','Hata':'Error','Uyarı':'Warning','Onay':'Confirm','Evet':'Yes','Hayır':'No','Seçiniz':'Select','Seç':'Select','Yükleniyor...':'Loading...','Aranıyor...':'Searching...','Kayıt bulunamadı':'No records found','Veri bulunamadı':'No data found','Zorunlu alan':'Required field','Lütfen bekleyin':'Please wait','Yenile':'Refresh','Geri':'Back','İleri':'Next','Bugün':'Today','Dün':'Yesterday','Bu Ay':'This Month','Bu Yıl':'This Year'
 },
 ar:{
  'Ana Sayfa':'الرئيسية','Çıkış İşlemleri':'عمليات الخروج','Giriş İşlemleri':'عمليات الدخول','Operasyon':'العمليات','Filo':'الأسطول','Şoförler':'السائقون','Bakım':'الصيانة','Raporlar':'التقارير','Ayarlar':'الإعدادات','Muhasebe & Finans':'المحاسبة والمالية','MUHASEBE & FİNANS':'المحاسبة والمالية','Günlük Kasa':'الصندوق اليومي','Avans Takip':'متابعة السلف','Kullanıcılar & Yetkiler':'المستخدمون والصلاحيات','Kullanıcı Adı':'اسم المستخدم','Şifre':'كلمة المرور','Giriş':'تسجيل الدخول','Çıkış':'تسجيل الخروج','Kaydet':'حفظ','İptal':'إلغاء','Kapat':'إغلاق','Düzenle':'تعديل','Sil':'حذف','Yeni Kayıt':'سجل جديد','Ara':'بحث','Tarih':'التاريخ','Plaka':'رقم المركبة','Şoför':'السائق','Tutar':'المبلغ','Açıklama':'الوصف','Durum':'الحالة','Beklemede':'في الانتظار','Bakımda':'في الصيانة','Yolda':'على الطريق','Boşta':'متاح','Gemide Çalışan':'يعمل على السفينة','Boşaltıldı Dönüyor':'تم التفريغ / عائد','Toplam':'المجموع','Para Birimi':'العملة','Yetkiler':'الصلاحيات','Kullanıcılar':'المستخدمون',
  'Sevkiyat':'الشحنة','Sevkiyatlar':'الشحنات','Yeni Sevkiyat':'شحنة جديدة','Yeni Sevkiyat Ekle':'إضافة شحنة جديدة','Çıkış':'خروج','Giriş':'دخول','Çıkış Tarihi':'تاريخ الخروج','Giriş Tarihi':'تاريخ الدخول','Çıkış Saati':'وقت الخروج','Giriş Saati':'وقت الدخول','Çıkış KM':'عداد الخروج','Giriş KM':'عداد الدخول','Müşteri':'العميل','Bölge':'المنطقة','Teslimat Bölgesi':'منطقة التسليم','Mal Tipi':'نوع الحمولة','Net KG':'الوزن الصافي','Navlun':'أجرة النقل','Navlun Birim Fiyat':'سعر وحدة النقل','Harcırah':'مخصصات','Prim':'مكافأة','Diğer':'أخرى','Not':'ملاحظة','Telefon':'الهاتف','D.No':'رقم السائق','Depo Mazot':'وقود الخزان','Resmi Mazot':'وقود رسمي','Ticari Mazot':'وقود تجاري','Bağdat Mazot':'وقود بغداد','Litre':'لتر','Birim Fiyat':'سعر الوحدة','Yakıt':'الوقود','Yakıt Alımı':'شراء الوقود','Tahsilat':'التحصيل','Kalan':'المتبقي','Getirilen Para':'النقد المعاد','Şoförün Getirdiği Para':'النقد الذي أعاده السائق','Şoförün Vermesi Gereken Para':'المبلغ المطلوب من السائق','Şoföre Verilmesi Gereken':'المبلغ المطلوب إعطاؤه للسائق','Çıkış Parası':'نقد الخروج','Çıkış Parası Eksik':'نقد الخروج مفقود',
  'Aktif':'نشط','Pasif':'غير نشط','Tamamlandı':'مكتمل','Bekliyor':'قيد الانتظار','Çıkışta':'في الخروج','Girişte':'في الدخول','TAMAMLANDI':'مكتمل','ÇIKIŞTA':'في الخروج','GİRİŞTE':'في الدخول','GEMİDE ÇALIŞIYOR':'يعمل على السفينة','BAKIMDA':'في الصيانة','YOLDA':'على الطريق','BOŞALTILDI DÖNÜYOR':'تم التفريغ / عائد','BEKLEMEDE':'في الانتظار','BOŞTA':'متاح',
  'Araç':'المركبة','Araçlar':'المركبات','Araç Ekle':'إضافة مركبة','Araç Düzenle':'تعديل المركبة','Marka':'الماركة','Model':'الموديل','Araç Tipi':'نوع المركبة','Garaj Durumu':'حالة المرآب','Gemi':'السفينة','Gemi Operasyonu':'عملية السفينة','Yükleme Sırası':'ترتيب التحميل','Sıra No':'رقم الدور','Operasyon Notu':'ملاحظة العملية','Filo Durumu':'حالة الأسطول','Araç Durumu':'حالة المركبة','GPS Durumu':'حالة GPS','Son Güncelleme':'آخر تحديث',
  'Şoför Ekle':'إضافة سائق','Şoför Düzenle':'تعديل السائق','Şoför No':'رقم السائق','Şoför Adı':'اسم السائق','Telefon No':'رقم الهاتف','Aktif Şoförler':'السائقون النشطون','Pasif Şoförler':'السائقون غير النشطين',
  'Bakım Kaydı':'سجل الصيانة','Aracı Bakıma Al':'إرسال المركبة للصيانة','Bakım Bitti':'انتهت الصيانة','Bakım Başlangıç':'بدء الصيانة','Bakım Bitiş':'نهاية الصيانة','Bakım Nedeni':'سبب الصيانة','Bakım Açıklaması':'وصف الصيانة','Yapılan İşlem':'العمل المنفذ','Tahmini Süre':'المدة التقديرية','Önceki Durum':'الحالة السابقة','DÜZENLE':'تعديل',
  'Rapor':'تقرير','Filtrele':'تصفية','Temizle':'مسح','Dışa Aktar':'تصدير','Excel Dışa Aktar':'تصدير Excel','Excel İçe Aktar':'استيراد Excel','İçe Aktar':'استيراد','Başlangıç Tarihi':'تاريخ البداية','Bitiş Tarihi':'تاريخ النهاية','Tarih Aralığı':'نطاق التاريخ','Tümü':'الكل','Sonuç':'النتيجة','Kayıt':'سجل','Kayıtlar':'السجلات','Kayıt Sayısı':'عدد السجلات','Toplam Kayıt':'إجمالي السجلات',
  'Gün Başı':'رصيد أول اليوم','Sevkiyattan Gelen':'الوارد من الشحنات','Diğer Kasa Girişi':'إدخال نقدي آخر','Diğer Giriş':'إدخال آخر','Sevkiyat Çıkışı / Şoföre Verilen':'خروج الشحنة / المدفوع للسائق','Avans':'سلفة','Avanslar':'السلف','Doğrudan Harcama':'مصروف مباشر','Harcama':'مصروف','Harcamalar':'المصروفات','Beklenen Kasa':'الرصيد المتوقع','Beklenen':'متوقع','Fiili Kasa':'النقد الفعلي','Fiili':'فعلي','Açık':'الفرق','Kasa':'الصندوق','Kasa Girişi':'دخول نقدي','Kasa Çıkışı':'خروج نقدي','Belge No':'رقم المستند','Fatura No':'رقم الفاتورة','Fiş No':'رقم الإيصال','Fatura':'فاتورة','Fiş':'إيصال','Nakit İade':'إرجاع نقدي','Mahsup':'تسوية','Belge Türü':'نوع المستند','Hesaplaşma':'تسوية','Hesaplaşmalar':'التسويات','Kalan Avans':'السلفة المتبقية','Avans Tutarı':'مبلغ السلفة','Avans Ver':'إعطاء سلفة','Avans Düzenle':'تعديل السلفة','Kişi':'الشخص','Kişi Tipi':'نوع الشخص','Usta':'فني','Personel':'موظف',
  'Kullanıcı':'المستخدم','Rol':'الدور','Yetki':'الصلاحية','Kullanıcı Ekle':'إضافة مستخدم','Kullanıcı Düzenle':'تعديل المستخدم','Şifre Değiştir':'تغيير كلمة المرور','Yeni Şifre':'كلمة المرور الجديدة','Mevcut Şifre':'كلمة المرور الحالية','Çıkış Yap':'تسجيل الخروج','Oturum':'الجلسة','Admin':'مدير','Operatör':'مشغل','İzleyici':'مشاهد',
  'İşlem Geçmişi':'سجل العمليات','İşlem':'العملية','Oluşturulma Tarihi':'تاريخ الإنشاء','Güncelleme Tarihi':'تاريخ التحديث','Detay':'التفاصيل','Silindi':'تم الحذف','Güncellendi':'تم التحديث','Eklendi':'تمت الإضافة','Başarılı':'نجاح','Hata':'خطأ','Uyarı':'تحذير','Onay':'تأكيد','Evet':'نعم','Hayır':'لا','Seçiniz':'اختر','Seç':'اختر','Yükleniyor...':'جارٍ التحميل...','Aranıyor...':'جارٍ البحث...','Kayıt bulunamadı':'لم يتم العثور على سجلات','Veri bulunamadı':'لا توجد بيانات','Zorunlu alan':'حقل مطلوب','Lütfen bekleyin':'يرجى الانتظار','Yenile':'تحديث','Geri':'رجوع','İleri':'التالي','Bugün':'اليوم','Dün':'أمس','Bu Ay':'هذا الشهر','Bu Yıl':'هذا العام'
 }
};
  // SAMA_I18N_FULL_TRANSLATION_V4
'''

s=s[:start]+block+s[end:]

fn_start=s.find('  function translateString(raw,l){')
fn_end=s.find('  function translateNode(', fn_start)
if fn_start<0 or fn_end<0:
    raise SystemExit('translateString function not found')
newfn=r'''  function translateString(raw,l){
    if(l==='tr'||raw==null)return raw;
    const text=String(raw), trimmed=text.trim();
    if(!trimmed)return raw;
    const dict=DICT[l]||{};
    if(Object.prototype.hasOwnProperty.call(dict,trimmed))return text.replace(trimmed,dict[trimmed]);
    let out=text;
    const keys=Object.keys(dict).filter(k=>k.length>=8||k.includes(' ')).sort((a,b)=>b.length-a.length);
    for(const k of keys){if(out.includes(k))out=out.split(k).join(dict[k]);}
    return out;
  }
'''
s=s[:fn_start]+newfn+s[fn_end:]

# Also translate aria-label attributes; useful for icon buttons and compact controls.
s=s.replace("for(const a of ['placeholder','title']){", "for(const a of ['placeholder','title','aria-label']){", 1)

p.write_text(s,encoding='utf-8')
print('patched')
