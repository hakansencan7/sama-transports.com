from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='// SAMA_I18N_TR_EN_AR_V1'
if MARK in s:
    print('already patched'); raise SystemExit
# Inject language selector before first closing body. Runtime translator intentionally translates text nodes + placeholders/buttons,
# so existing UI remains source-of-truth and new screens still degrade safely to Turkish.
block=r'''
<style id="sama-i18n-style">
#samaLangBox{position:fixed;right:18px;top:12px;z-index:10050;display:flex;gap:4px;padding:4px;border-radius:10px;background:rgba(15,23,42,.92);box-shadow:0 4px 16px rgba(0,0,0,.18)}
#samaLangBox button{border:0;border-radius:7px;padding:6px 9px;cursor:pointer;font-weight:700;background:transparent;color:#cbd5e1}
#samaLangBox button.active{background:#2563eb;color:white}
html[dir="rtl"] body{direction:rtl;text-align:right} html[dir="rtl"] #samaLangBox{right:auto;left:18px}
</style>
<div id="samaLangBox" aria-label="Language"><button data-lang="tr">TR</button><button data-lang="en">EN</button><button data-lang="ar">AR</button></div>
<script>
// SAMA_I18N_TR_EN_AR_V1
(function(){
const D={
 en:{'Ana Sayfa':'Dashboard','Çıkış İşlemleri':'Exit Operations','Giriş İşlemleri':'Entry Operations','Operasyon':'Operations','Filo':'Fleet','Şoförler':'Drivers','Bakım':'Maintenance','Raporlar':'Reports','Ayarlar':'Settings','Muhasebe & Finans':'Accounting & Finance','MUHASEBE & FİNANS':'ACCOUNTING & FINANCE','Günlük Kasa':'Daily Cash','Avans Takip':'Advance Tracking','Kullanıcılar & Yetkiler':'Users & Permissions','Kullanıcı Adı':'Username','Şifre':'Password','Giriş':'Login','Çıkış':'Logout','Kaydet':'Save','İptal':'Cancel','Kapat':'Close','Düzenle':'Edit','Sil':'Delete','Yeni Kayıt':'New Record','Ara':'Search','Tarih':'Date','Plaka':'Plate','Şoför':'Driver','Tutar':'Amount','Açıklama':'Description','Durum':'Status','Beklemede':'Waiting','Bakımda':'Maintenance','Yolda':'On Road','Boşta':'Available','Gemide Çalışan':'Working on Ship','Boşaltıldı Dönüyor':'Unloaded / Returning','Toplam':'Total','Para Birimi':'Currency','Yetkiler':'Permissions','Kullanıcılar':'Users'},
 ar:{'Ana Sayfa':'الرئيسية','Çıkış İşlemleri':'عمليات الخروج','Giriş İşlemleri':'عمليات الدخول','Operasyon':'العمليات','Filo':'الأسطول','Şoförler':'السائقون','Bakım':'الصيانة','Raporlar':'التقارير','Ayarlar':'الإعدادات','Muhasebe & Finans':'المحاسبة والمالية','MUHASEBE & FİNANS':'المحاسبة والمالية','Günlük Kasa':'الصندوق اليومي','Avans Takip':'متابعة السلف','Kullanıcılar & Yetkiler':'المستخدمون والصلاحيات','Kullanıcı Adı':'اسم المستخدم','Şifre':'كلمة المرور','Giriş':'تسجيل الدخول','Çıkış':'تسجيل الخروج','Kaydet':'حفظ','İptal':'إلغاء','Kapat':'إغلاق','Düzenle':'تعديل','Sil':'حذف','Yeni Kayıt':'سجل جديد','Ara':'بحث','Tarih':'التاريخ','Plaka':'رقم المركبة','Şoför':'السائق','Tutar':'المبلغ','Açıklama':'الوصف','Durum':'الحالة','Beklemede':'في الانتظار','Bakımda':'في الصيانة','Yolda':'على الطريق','Boşta':'متاح','Gemide Çalışan':'يعمل على السفينة','Boşaltıldı Dönüyor':'تم التفريغ / عائد','Toplam':'المجموع','Para Birimi':'العملة','Yetkiler':'الصلاحيات','Kullanıcılar':'المستخدمون'}
};
const original=new WeakMap();
function transText(v,lang){let x=(v||'').trim(); if(lang==='tr'||!x)return v; let z=D[lang]&&D[lang][x]; if(!z)return v; return v.replace(x,z)}
function apply(lang){
 lang=['tr','en','ar'].includes(lang)?lang:'tr'; localStorage.setItem('sama_lang',lang);
 document.documentElement.lang=lang; document.documentElement.dir=lang==='ar'?'rtl':'ltr';
 document.querySelectorAll('#samaLangBox button').forEach(b=>b.classList.toggle('active',b.dataset.lang===lang));
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT); let n;
 while(n=walker.nextNode()){if(n.parentElement&&n.parentElement.closest('#samaLangBox,script,style'))continue;if(!original.has(n))original.set(n,n.nodeValue);n.nodeValue=transText(original.get(n),lang)}
 document.querySelectorAll('input,textarea,button,[title]').forEach(el=>{['placeholder','title','value'].forEach(a=>{if(a==='value'&&!(el.tagName==='INPUT'&&['button','submit'].includes(el.type)))return;let key='i18n_'+a;if(el.hasAttribute(a)){if(!el.dataset[key])el.dataset[key]=el.getAttribute(a);el.setAttribute(a,transText(el.dataset[key],lang))}})});
}
window.setSamaLanguage=apply;
document.querySelectorAll('#samaLangBox button').forEach(b=>b.addEventListener('click',()=>apply(b.dataset.lang)));
const obs=new MutationObserver(()=>{clearTimeout(window._samaI18nT);window._samaI18nT=setTimeout(()=>apply(localStorage.getItem('sama_lang')||'tr'),30)});obs.observe(document.body,{childList:true,subtree:true});
apply(localStorage.getItem('sama_lang')||'tr');
})();
</script>
'''
pos=s.lower().rfind('</body>')
if pos<0: raise SystemExit('closing body not found')
s=s[:pos]+block+s[pos:]
p.write_text(s,encoding='utf-8')
print('patched')
# trigger: 2026-09-01
