# SAMA TRACK - Shipment Edit Center monetary visibility patch
#
# The authoritative Edit Center already saves the common TripEditIn money fields.
# This layer does not create a second save flow. It makes those fields unmistakable,
# adds IQD markers, and shows the money that lives only in Exit/Entry subflows
# (fuel totals, exit cash, fixed Entry expense metadata, Entry OTHER, road fuel).
#
# Important: app.py declares `let editCx`, which is NOT `window.editCx` in browsers.
# Earlier versions of this patch therefore missed the currently loaded trip.

import shipment_scna_rename_patch as base

app = base.app
core = base.core
html = core.HTML

helper = r'''
function samaEditCurrentTrip(){
  try{
    if(typeof editCx!=='undefined' && editCx) return editCx;
  }catch(_e){}
  return null;
}
function samaEditCurrentScna(){
  const t=samaEditCurrentTrip();
  if(t && t.scna) return String(t.scna).trim().toUpperCase();
  try{
    if(typeof editScna!=='undefined' && editScna) return String(editScna.value||'').trim().toUpperCase();
  }catch(_e){}
  return '';
}
function samaMoneyNum(v){
  try{if(typeof parseMoney==='function')return Number(parseMoney(v||0)||0);}catch(_e){}
  const s=String(v??'').trim().replace(/\s/g,'');
  if(!s)return 0;
  if(/^[-+]?\d{1,3}([.,]\d{3})+$/.test(s))return Number(s.replace(/[.,]/g,''))||0;
  return Number(s.replace(/\./g,'').replace(',','.'))||0;
}
function samaMoneyFmt(v){
  const n=Number(v||0);
  try{return new Intl.NumberFormat('tr-TR',{maximumFractionDigits:2}).format(n)+' IQD';}
  catch(_e){return String(n)+' IQD';}
}
function samaMoneyClass(v){
  const n=Number(v||0);
  return n<0?'sama-money-neg':(n>0?'sama-money-pos':'');
}
function samaEditInputMoney(id,fallback=0){
  const el=document.getElementById(id);
  return el?samaMoneyNum(el.value):Number(fallback||0);
}
function samaEscMoneyText(v){
  return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

const SAMA_EDIT_MONEY_FIELDS={
  eRate:'Navlun Birim Fiyat',
  ePremium:'Prim',
  eDock:'Dock Fee',
  ePort:'Port Fee',
  eSonar:'SONAR',
  eAllowance:'Harcırah',
  eOther:'Çıkış OTHER',
  eExtra1:'Kantar / Giriş Gider 1',
  eExtra2:'Park / Giriş Gider 2',
  eExtra3:'Bekleme / Giriş Gider 3',
  eCollection:'Müşteriden Alınan Para',
  eHand:'Şoförün Verdiği Para'
};
function samaMarkEditMoneyFields(){
  Object.entries(SAMA_EDIT_MONEY_FIELDS).forEach(([id,label])=>{
    const el=document.getElementById(id);if(!el)return;
    const field=el.closest('.field');
    if(field)field.classList.add('sama-edit-money-field');
    const lab=field?.querySelector('label');
    if(lab && !lab.querySelector('.sama-iqd-tag')){
      const tag=document.createElement('span');tag.className='sama-iqd-tag';tag.textContent='IQD';lab.appendChild(tag);
    }
    if(!el.dataset.samaMoneyLive){
      el.addEventListener('input',()=>samaRefreshMoneySummary());
      el.dataset.samaMoneyLive='1';
    }
  });
}

function samaMoneyRow(label,value,extra=''){
  const n=Number(value||0);
  return '<div class="sama-money-row"><span>'+label+(extra?'<small>'+extra+'</small>':'')+'</span><strong class="'+samaMoneyClass(n)+'">'+samaMoneyFmt(n)+'</strong></div>';
}
function samaMoneyInfoRow(label,value,extra=''){
  return '<div class="sama-money-row sama-money-readonly"><span>'+label+(extra?'<small>'+extra+'</small>':'')+'</span><strong>'+samaMoneyFmt(value)+'</strong></div>';
}

function samaRefreshMoneySummary(){
  const t=samaEditCurrentTrip();if(!t)return;
  const map={
    sumRate:samaEditInputMoney('eRate',t.freight_rate),
    sumPremium:samaEditInputMoney('ePremium',t.exit_premium),
    sumDock:samaEditInputMoney('eDock',t.dock_fee),
    sumPort:samaEditInputMoney('ePort',t.port_fee),
    sumSonar:samaEditInputMoney('eSonar',t.sonar),
    sumAllowance:samaEditInputMoney('eAllowance',t.exit_allowance),
    sumExitOther:samaEditInputMoney('eOther',t.exit_other),
    sumExtra1:samaEditInputMoney('eExtra1',t.entry_extra_expense_1),
    sumExtra2:samaEditInputMoney('eExtra2',t.entry_extra_expense_2),
    sumExtra3:samaEditInputMoney('eExtra3',t.entry_extra_expense_3),
    sumCollection:samaEditInputMoney('eCollection',t.entry_collection),
    sumHand:samaEditInputMoney('eHand',t.entry_cash_handed)
  };
  Object.entries(map).forEach(([id,v])=>{
    const e=document.getElementById(id);if(!e)return;
    e.textContent=samaMoneyFmt(v);e.classList.remove('sama-money-pos','sama-money-neg');
    const cls=samaMoneyClass(v);if(cls)e.classList.add(cls);
  });
  const editableExit=map.sumPremium+map.sumDock+map.sumPort+map.sumSonar+map.sumAllowance+map.sumExitOther;
  const editableEntry=map.sumExtra1+map.sumExtra2+map.sumExtra3;
  const a=document.getElementById('sumEditableExit');if(a)a.textContent=samaMoneyFmt(editableExit);
  const b=document.getElementById('sumEditableEntry');if(b)b.textContent=samaMoneyFmt(editableEntry);
}

async function samaLoadEditMoneyExtras(scna){
  const fixedBox=document.getElementById('samaMoneyFixedRows');
  const otherBox=document.getElementById('samaMoneyOtherRows');
  const roadBox=document.getElementById('samaMoneyRoadFuel');
  if(!scna)return;

  try{
    const rows=await api('/api/trips/'+encodeURIComponent(scna)+'/entry-fixed-expenses');
    if(fixedBox){
      const names={1:'KANTAR / WEIGHBRIDGE',2:'PARK / PARKING',3:'BEKLEME / WAITING'};
      fixedBox.innerHTML=(rows||[]).length?(rows||[]).map(x=>
        '<div class="sama-money-row sama-money-readonly"><span>'+samaEscMoneyText(names[Number(x.slot)]||x.code||('Gider '+x.slot))+
        '<small>'+Number(x.qty||0).toLocaleString('tr-TR')+' × '+samaMoneyFmt(x.unit_price||0)+'</small></span><strong>'+samaMoneyFmt(x.total||0)+'</strong></div>'
      ).join(''):'<div class="sama-money-empty">Kayıtlı sabit giriş gideri yok.</div>';
    }
  }catch(_e){if(fixedBox)fixedBox.innerHTML='<div class="sama-money-empty">Sabit giriş giderleri okunamadı.</div>';}

  try{
    const rows=await api('/api/trips/'+encodeURIComponent(scna)+'/entry-other-expenses');
    if(otherBox){
      const active=(rows||[]).filter(x=>Number(x.amount||0)!==0||String(x.description||'').trim());
      otherBox.innerHTML=active.length?active.map(x=>
        '<div class="sama-money-row sama-money-readonly"><span>OTHER / DİĞER '+Number(x.slot||0)+
        '<small>'+samaEscMoneyText(x.description||'Açıklama yok')+'</small></span><strong>'+samaMoneyFmt(x.amount||0)+'</strong></div>'
      ).join(''):'<div class="sama-money-empty">Kayıtlı Giriş OTHER gideri yok.</div>';
    }
  }catch(_e){if(otherBox)otherBox.innerHTML='<div class="sama-money-empty">Giriş OTHER kayıtları okunamadı.</div>';}

  try{
    const rows=await api('/api/trips/'+encodeURIComponent(scna)+'/fuel');
    const total=(rows||[]).reduce((s,x)=>s+Number(x.total||0),0);
    const liters=(rows||[]).reduce((s,x)=>s+Number(x.liters||0),0);
    if(roadBox){
      roadBox.innerHTML='<div class="sama-money-row sama-money-readonly"><span>Yolda Alınan Ek Mazot<small>'+Number(liters||0).toLocaleString('tr-TR',{maximumFractionDigits:2})+' LT</small></span><strong>'+samaMoneyFmt(total)+'</strong></div>';
    }
  }catch(_e){if(roadBox)roadBox.innerHTML='<div class="sama-money-empty">Yol mazotu okunamadı.</div>';}
}

function samaEditMoneyPanel(trip){
  trip=trip||samaEditCurrentTrip()||{};
  const old=document.getElementById('samaEditMoneyPanel');if(old)old.remove();
  const anchor=document.getElementById('editValidation') || document.getElementById('editCenterContent') || document.querySelector('#editcenter .card') || document.querySelector('#editcenter');
  if(!anchor)return;

  const exitFuel=Number(trip.exit_official_fuel_total||0)+Number(trip.exit_commercial_fuel_total||0)+Number(trip.exit_baghdad_fuel_total||0);
  const panel=document.createElement('div');panel.id='samaEditMoneyPanel';panel.className='sama-edit-money-panel';
  panel.innerHTML=`
    <div class="sama-money-head">
      <div><b>💰 PARASAL BİLGİLER</b><span>GİRİŞ + ÇIKIŞ</span></div>
      <div class="sama-money-legend"><i></i>Düzenlenebilir <i class="gray"></i>Bilgi amaçlı</div>
    </div>
    <div class="sama-money-help"><b>Turuncu işaretli para kutuları</b> normal DÜZENLE / KAYDET ile aynı sevkiyata kaydolur. Gri satırlar Giriş veya Çıkış ekranındaki ayrı kayıtlardan okunur ve burada yanlışlıkla sıfırlanmaz.</div>

    <div class="sama-money-columns">
      <section>
        <h4>ÇIKIŞ PARASAL</h4>
        ${samaMoneyRow('Prim',trip.exit_premium)}
        ${samaMoneyRow('Harcırah',trip.exit_allowance)}
        ${samaMoneyRow('Dock Fee',trip.dock_fee)}
        ${samaMoneyRow('Port Fee',trip.port_fee)}
        ${samaMoneyRow('SONAR',trip.sonar)}
        ${samaMoneyRow('Çıkış OTHER',trip.exit_other)}
        <div class="sama-money-row sama-money-total"><span>Düzenlenebilir Çıkış Toplamı</span><strong id="sumEditableExit">0 IQD</strong></div>
        ${samaMoneyInfoRow('Şoföre Verilen Nakit',trip.exit_cash,'Çıkış ekranından düzenlenir')}
        ${samaMoneyInfoRow('Resmî Mazot Tutarı',trip.exit_official_fuel_total)}
        ${samaMoneyInfoRow('Ticari Mazot Tutarı',trip.exit_commercial_fuel_total)}
        ${samaMoneyInfoRow('Bağdat Mazot Tutarı',trip.exit_baghdad_fuel_total)}
        ${samaMoneyInfoRow('Çıkış Mazot Toplamı',exitFuel)}
        <div id="samaMoneyRoadFuel"></div>
      </section>

      <section>
        <h4>GİRİŞ PARASAL</h4>
        ${samaMoneyRow('Kantar / Gider 1',trip.entry_extra_expense_1)}
        ${samaMoneyRow('Park / Gider 2',trip.entry_extra_expense_2)}
        ${samaMoneyRow('Bekleme / Gider 3',trip.entry_extra_expense_3)}
        <div class="sama-money-row sama-money-total"><span>Düzenlenebilir Giriş Gider Toplamı</span><strong id="sumEditableEntry">0 IQD</strong></div>
        ${samaMoneyRow('Müşteriden Alınan Para',trip.entry_collection)}
        ${samaMoneyRow('Şoförün Verdiği Para',trip.entry_cash_handed)}
        <div class="sama-money-subtitle">SABİT GİDER DETAYI <small>Giriş ekranından miktar × fiyat olarak düzenlenir</small></div>
        <div id="samaMoneyFixedRows"><div class="sama-money-empty">Yükleniyor...</div></div>
        <div class="sama-money-subtitle">GİRİŞ OTHER / DİĞER <small>Giriş ekranından düzenlenir</small></div>
        <div id="samaMoneyOtherRows"><div class="sama-money-empty">Yükleniyor...</div></div>
      </section>

      <section>
        <h4>GELİR / EXCEL</h4>
        ${samaMoneyRow('Navlun Birim Fiyatı',trip.freight_rate)}
        ${samaMoneyInfoRow('Excel PRICE K',trip.excel_price_k)}
        ${samaMoneyInfoRow('Excel FREIGHT AU',trip.excel_freight_au)}
        ${samaMoneyInfoRow('Excel AMOUNT',trip.excel_amount)}
        ${samaMoneyInfoRow('Excel REMAIN',trip.excel_remain)}
      </section>
    </div>

    <div style="display:none">
      <b id="sumRate"></b><b id="sumPremium"></b><b id="sumDock"></b><b id="sumPort"></b><b id="sumSonar"></b><b id="sumAllowance"></b><b id="sumExitOther"></b>
      <b id="sumExtra1"></b><b id="sumExtra2"></b><b id="sumExtra3"></b><b id="sumCollection"></b><b id="sumHand"></b>
    </div>`;

  if(anchor.id==='editValidation' && anchor.parentElement)anchor.parentElement.insertBefore(panel,anchor.nextSibling);
  else anchor.prepend(panel);
  samaMarkEditMoneyFields();
  samaRefreshMoneySummary();
  samaLoadEditMoneyExtras(String(trip.scna||samaEditCurrentScna()));
}

function samaEditMoneyBoot(){
  let lastScna='';
  setInterval(()=>{
    try{
      const trip=samaEditCurrentTrip();
      const scna=samaEditCurrentScna();
      if(!trip||!scna){lastScna='';return;}
      samaMarkEditMoneyFields();
      if(scna!==lastScna || !document.getElementById('samaEditMoneyPanel')){
        lastScna=scna;
        samaEditMoneyPanel(trip);
      }
    }catch(_e){}
  },250);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',samaEditMoneyBoot);else samaEditMoneyBoot();
'''

css = r'''
.sama-edit-money-field{border:1px solid #f59e0b!important;background:#fffbeb!important;border-radius:10px!important;padding:7px!important}.sama-edit-money-field label{display:flex!important;justify-content:space-between!important;gap:7px!important;align-items:center!important}.sama-iqd-tag{font-size:9px;font-weight:950;letter-spacing:.3px;background:#f59e0b;color:#111827;border-radius:999px;padding:2px 6px}.sama-edit-money-panel{margin:14px 0;border:2px solid #d97706;border-radius:15px;background:#fffbeb;padding:13px}.sama-money-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.sama-money-head>div:first-child{display:flex;gap:8px;align-items:center}.sama-money-head b{font-size:16px}.sama-money-head span{font-size:10px;font-weight:900;background:#fef3c7;border-radius:999px;padding:4px 7px}.sama-money-legend{font-size:10px;display:flex;gap:5px;align-items:center;color:#64748b}.sama-money-legend i{width:10px;height:10px;border-radius:3px;background:#f59e0b;display:inline-block}.sama-money-legend i.gray{background:#cbd5e1;margin-left:6px}.sama-money-help{font-size:11px;margin:9px 0 12px;padding:9px;border-radius:9px;background:#fff7d6;color:#6b4e00}.sama-money-columns{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.sama-money-columns section{background:var(--card,#fff);border:1px solid var(--border,#d8dee6);border-radius:12px;padding:10px;min-width:0}.sama-money-columns h4{margin:0 0 7px;font-size:12px;color:#92400e}.sama-money-row{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px dashed #d7dde5;font-size:11px;align-items:center}.sama-money-row span{min-width:0}.sama-money-row small{display:block;color:#64748b;font-size:9px;margin-top:2px;white-space:normal}.sama-money-row strong{font-size:12px;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}.sama-money-readonly{background:#f8fafc;margin:0 -4px;padding-left:4px;padding-right:4px}.sama-money-readonly strong{color:#475569}.sama-money-total{border-top:2px solid #f59e0b;border-bottom:0;margin-top:3px;font-weight:900}.sama-money-pos{color:#15803d!important}.sama-money-neg{color:#b91c1c!important}.sama-money-subtitle{margin-top:10px;font-size:10px;font-weight:950;color:#334155}.sama-money-subtitle small{display:block;font-size:9px;font-weight:600;color:#64748b;margin-top:2px}.sama-money-empty{font-size:10px;color:#64748b;padding:6px 0}@media(max-width:1150px){.sama-money-columns{grid-template-columns:1fr 1fr}}@media(max-width:760px){.sama-money-columns{grid-template-columns:1fr}.sama-money-head{align-items:flex-start;flex-direction:column}}
'''
if '</style>' in html and '.sama-edit-money-panel{' not in html:
    html = html.replace('</style>', css + '</style>', 1)

# Keep all JS in the established main script. A second script block would be more
# fragile with the app's long patch chain.
marker = 'async function kbLoadSingleV2(){'
inserted = False
if marker in html and 'function samaEditCurrentTrip' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)
    inserted = True

core.HTML = html
print(f'[SAMA] Shipment Edit money visibility V2 active: js={1 if inserted else 0}')
