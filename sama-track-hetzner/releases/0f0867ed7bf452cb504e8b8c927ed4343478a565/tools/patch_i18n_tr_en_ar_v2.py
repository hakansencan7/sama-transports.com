from pathlib import Path

p = Path('app.py')
s = p.read_text(encoding='utf-8')
MARK = '// SAMA_I18N_TR_EN_AR_V2'

if MARK in s:
    print('already patched')
    raise SystemExit(0)

main_anchor = 'HTML = r"""'
main_pos = s.find(main_anchor)
if main_pos < 0:
    raise SystemExit('main HTML anchor not found')

body_pos = s.lower().find('<body', main_pos)
if body_pos < 0:
    raise SystemExit('main body not found')
body_end = s.find('>', body_pos)
if body_end < 0:
    raise SystemExit('main body opening tag malformed')

block = r'''
<!-- SAMA main UI language selector -->
<style id="sama-i18n-style-v2">
#samaLangBox{position:fixed;right:18px;top:12px;z-index:10050;display:flex;align-items:center;gap:4px;padding:4px;border:1px solid rgba(148,163,184,.25);border-radius:10px;background:rgba(15,23,42,.94);box-shadow:0 5px 18px rgba(0,0,0,.22);backdrop-filter:blur(7px)}
#samaLangBox button{border:0;border-radius:7px;padding:6px 9px;min-width:34px;cursor:pointer;font-weight:800;font-size:12px;line-height:1.1;background:transparent;color:#cbd5e1}
#samaLangBox button:hover{background:rgba(255,255,255,.10);color:#fff}
#samaLangBox button.active{background:#2563eb;color:#fff}
html[dir="rtl"] body{direction:rtl;text-align:right}
html[dir="rtl"] #samaLangBox{right:auto;left:18px}
@media(max-width:760px){#samaLangBox{right:8px;top:8px;transform:scale(.92);transform-origin:top right}html[dir="rtl"] #samaLangBox{right:auto;left:8px;transform-origin:top left}}
</style>
<div id="samaLangBox" aria-label="Language selector">
  <button type="button" data-lang="tr" title="Türkçe">TR</button>
  <button type="button" data-lang="en" title="English">EN</button>
  <button type="button" data-lang="ar" title="العربية">AR</button>
</div>
<script>
// SAMA_I18N_TR_EN_AR_V2
(function(){
  const DICT={
    en:{
      'Ana Sayfa':'Dashboard','Çıkış İşlemleri':'Exit Operations','Giriş İşlemleri':'Entry Operations','Operasyon':'Operations','Filo':'Fleet','Şoförler':'Drivers','Bakım':'Maintenance','Raporlar':'Reports','Ayarlar':'Settings','Muhasebe & Finans':'Accounting & Finance','MUHASEBE & FİNANS':'ACCOUNTING & FINANCE','Günlük Kasa':'Daily Cash','Avans Takip':'Advance Tracking','Kullanıcılar & Yetkiler':'Users & Permissions','Kullanıcı Adı':'Username','Şifre':'Password','Giriş':'Login','Çıkış':'Logout','Kaydet':'Save','İptal':'Cancel','Kapat':'Close','Düzenle':'Edit','DÜZENLE':'EDIT','Sil':'Delete','Yeni Kayıt':'New Record','Ara':'Search','Tarih':'Date','Plaka':'Plate','PLAKA':'PLATE','Şoför':'Driver','ŞOFÖR':'DRIVER','Tutar':'Amount','Açıklama':'Description','Durum':'Status','Beklemede':'Waiting','BEKLEMEDE':'WAITING','Bakımda':'Maintenance','BAKIMDA':'MAINTENANCE','Yolda':'On Road','YOLDA':'ON ROAD','Boşta':'Available','BOŞTA':'AVAILABLE','Gemide Çalışan':'Working on Ship','GEMİDE ÇALIŞIYOR':'WORKING ON SHIP','Boşaltıldı Dönüyor':'Unloaded / Returning','BOŞALTILDI DÖNÜYOR':'UNLOADED / RETURNING','Toplam':'Total','Para Birimi':'Currency','Yetkiler':'Permissions','Kullanıcılar':'Users','Müşteri':'Customer','MÜŞTERİ':'CUSTOMER','Bölge':'Area','BÖLGE':'AREA','Gemi':'Vessel','GEMİ':'VESSEL','Kasa':'Cash','Harcama':'Expense','Harcamalar':'Expenses','Gün Başı':'Opening Cash','Beklenen':'Expected','Fiili':'Actual','Açık':'Difference','Not':'Note','İşlem':'Action','İŞLEM':'ACTION','Aktif':'Active','Pasif':'Inactive','Tamamlandı':'Completed','TAMAMLANDI':'COMPLETED','Yüklemede':'Loading','YÜKLEMEDE':'LOADING','Sıra Bekliyor':'Waiting Queue','SIRA BEKLİYOR':'WAITING QUEUE','Boş':'Empty','BOŞ':'EMPTY','Dolu':'Loaded','DOLU':'LOADED'
    },
    ar:{
      'Ana Sayfa':'الرئيسية','Çıkış İşlemleri':'عمليات الخروج','Giriş İşlemleri':'عمليات الدخول','Operasyon':'العمليات','Filo':'الأسطول','Şoförler':'السائقون','Bakım':'الصيانة','Raporlar':'التقارير','Ayarlar':'الإعدادات','Muhasebe & Finans':'المحاسبة والمالية','MUHASEBE & FİNANS':'المحاسبة والمالية','Günlük Kasa':'الصندوق اليومي','Avans Takip':'متابعة السلف','Kullanıcılar & Yetkiler':'المستخدمون والصلاحيات','Kullanıcı Adı':'اسم المستخدم','Şifre':'كلمة المرور','Giriş':'تسجيل الدخول','Çıkış':'تسجيل الخروج','Kaydet':'حفظ','İptal':'إلغاء','Kapat':'إغلاق','Düzenle':'تعديل','DÜZENLE':'تعديل','Sil':'حذف','Yeni Kayıt':'سجل جديد','Ara':'بحث','Tarih':'التاريخ','Plaka':'رقم المركبة','PLAKA':'رقم المركبة','Şoför':'السائق','ŞOFÖR':'السائق','Tutar':'المبلغ','Açıklama':'الوصف','Durum':'الحالة','Beklemede':'في الانتظار','BEKLEMEDE':'في الانتظار','Bakımda':'في الصيانة','BAKIMDA':'في الصيانة','Yolda':'على الطريق','YOLDA':'على الطريق','Boşta':'متاح','BOŞTA':'متاح','Gemide Çalışan':'يعمل على السفينة','GEMİDE ÇALIŞIYOR':'يعمل على السفينة','Boşaltıldı Dönüyor':'تم التفريغ / عائد','BOŞALTILDI DÖNÜYOR':'تم التفريغ / عائد','Toplam':'المجموع','Para Birimi':'العملة','Yetkiler':'الصلاحيات','Kullanıcılar':'المستخدمون','Müşteri':'العميل','MÜŞTERİ':'العميل','Bölge':'المنطقة','BÖLGE':'المنطقة','Gemi':'السفينة','GEMİ':'السفينة','Kasa':'الصندوق','Harcama':'مصروف','Harcamalar':'المصروفات','Gün Başı':'رصيد بداية اليوم','Beklenen':'المتوقع','Fiili':'الفعلي','Açık':'الفرق','Not':'ملاحظة','İşlem':'الإجراء','İŞLEM':'الإجراء','Aktif':'نشط','Pasif':'غير نشط','Tamamlandı':'مكتمل','TAMAMLANDI':'مكتمل','Yüklemede':'قيد التحميل','YÜKLEMEDE':'قيد التحميل','Sıra Bekliyor':'بانتظار الدور','SIRA BEKLİYOR':'بانتظار الدور','Boş':'فارغ','BOŞ':'فارغ','Dolu':'محمل','DOLU':'محمل'
    }
  };
  const originals=new WeakMap();
  const attrOriginals=new WeakMap();
  function lang(){const x=localStorage.getItem('sama_lang');return ['tr','en','ar'].includes(x)?x:'tr'}
  function translateString(value,l){
    const raw=value==null?'':String(value), key=raw.trim();
    if(l==='tr'||!key)return raw;
    const translated=DICT[l]&&DICT[l][key];
    return translated?raw.replace(key,translated):raw;
  }
  function translateNode(node,l){
    if(!node||!node.parentElement||node.parentElement.closest('#samaLangBox,script,style,noscript'))return;
    if(!originals.has(node))originals.set(node,node.nodeValue);
    node.nodeValue=translateString(originals.get(node),l);
  }
  function translateAttrs(el,l){
    if(!el||el.closest('#samaLangBox'))return;
    let store=attrOriginals.get(el);if(!store){store={};attrOriginals.set(el,store)}
    for(const a of ['placeholder','title']){
      if(el.hasAttribute(a)){if(!(a in store))store[a]=el.getAttribute(a);el.setAttribute(a,translateString(store[a],l))}
    }
    if(el.tagName==='INPUT'&&['button','submit','reset'].includes((el.type||'').toLowerCase())&&el.hasAttribute('value')){
      if(!('value' in store))store.value=el.getAttribute('value');el.setAttribute('value',translateString(store.value,l));
    }
  }
  function applyLanguage(l){
    l=['tr','en','ar'].includes(l)?l:'tr';
    localStorage.setItem('sama_lang',l);
    document.documentElement.lang=l;document.documentElement.dir=l==='ar'?'rtl':'ltr';
    document.querySelectorAll('#samaLangBox button').forEach(b=>b.classList.toggle('active',b.dataset.lang===l));
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;
    while((n=walker.nextNode()))translateNode(n,l);
    document.querySelectorAll('input,textarea,button,[title]').forEach(el=>translateAttrs(el,l));
  }
  window.setSamaLanguage=applyLanguage;
  document.querySelectorAll('#samaLangBox button').forEach(b=>b.addEventListener('click',()=>applyLanguage(b.dataset.lang)));
  let timer=null;
  new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(()=>applyLanguage(lang()),40)}).observe(document.body,{childList:true,subtree:true});
  applyLanguage(lang());
})();
</script>
'''

insert_at = body_end + 1
s = s[:insert_at] + block + s[insert_at:]
p.write_text(s, encoding='utf-8')

# Verify placement is inside the main HTML template, not DRIVER_HTML or print popups.
new_main_pos = s.find(main_anchor)
new_mark_pos = s.find(MARK)
if not (new_main_pos >= 0 and new_mark_pos > new_main_pos):
    raise SystemExit('language marker was not inserted into main HTML')
print('patched main HTML at', new_mark_pos)
