# Final Entry usability fix:
# - OTHER / DİĞER amounts participate in the Entry calculation immediately.
# - Completed Entry records open in review/locked mode and expose an explicit DÜZELT button.
# - DÜZELT unlocks only real Entry-edit fields; informational fields stay read-only.
# - OTHER and fixed expenses are flushed before the normal Entry save callback runs.
# No separate <script> block is added; helpers are inserted into the existing main JS.
import cash_daily_history_search_patch as base

app = base.app
core = base.core
html = core.HTML

helper = r'''
function samaEntryCanEdit(){
  try{if(typeof hasPerm==='function')return !!hasPerm('shipment.edit');}catch(_e){}
  try{return String(window.AUTH_USER?.role||AUTH_USER?.role||'').toUpperCase()==='ADMIN';}catch(_e){return false;}
}
function samaEntryEditIds(){
  return [
    'gKm','gTankEnd','gExtra1','gExtra2','gExtra3','gCollect','gHand','gNote',
    'fixedQty1','fixedPrice1','fixedQty2','fixedPrice2','fixedQty3','fixedPrice3',
    'entryOtherAmount1','entryOtherNote1','entryOtherAmount2','entryOtherNote2',
    'fLit','fTotal','fNote'
  ];
}
function samaEntrySetEditable(on){
  samaEntryEditIds().forEach(id=>{const el=document.getElementById(id);if(el)el.disabled=!on;});
  const addFuelBtn=[...document.querySelectorAll('#mBody button, #modal button')].find(b=>String(b.getAttribute('onclick')||'').includes('addFuel('));
  if(addFuelBtn)addFuelBtn.disabled=!on;
  ['entryOtherAmount1','entryOtherNote1','entryOtherAmount2','entryOtherNote2'].forEach(id=>{
    const el=document.getElementById(id);if(el){el.disabled=!on;el.readOnly=!on;el.style.opacity=on?'1':'0.68';}
  });
}
function samaEntryFlushExtras(){
  try{
    [1,2,3].forEach(slot=>{
      if(typeof fixedEntryRecalc==='function')fixedEntryRecalc(slot,false);
    });
    if(typeof entryOtherRecalc==='function')entryOtherRecalc(true);
  }catch(_e){}
}
async function samaEntryFlushExtrasAsync(){
  samaEntryFlushExtras();
  try{if(typeof fixedEntrySave==='function')for(const slot of [1,2,3])await fixedEntrySave(slot);}catch(_e){}
  try{if(typeof entryOtherSave==='function')for(const slot of [1,2])await entryOtherSave(slot);}catch(_e){}
}
function samaEntryUnlockEdit(){
  if(!samaEntryCanEdit()){alert('Bu kayıt için Giriş düzenleme yetkiniz yok.');return;}
  if(!window.cx)return;
  const modalEl=document.getElementById('modal')||window.modal;
  if(modalEl)modalEl.dataset.samaEntryUnlocked='1';
  samaEntrySetEditable(true);
  if(window.mSave){mSave.disabled=false;mSave.style.opacity='1';mSave.style.pointerEvents='auto';}
  const b=document.getElementById('samaEntryEditBtn');
  if(b){b.textContent='DÜZELTME MODU AÇIK';b.disabled=true;b.style.opacity='.75';}
  const info=document.getElementById('samaEntryEditInfo');
  if(info)info.innerHTML='<b>DÜZELTME MODU AÇIK.</b> Değişiklikleri yaptıktan sonra KAYDET ile tamamlayın.';
  try{if(typeof entryOtherRecalc==='function')entryOtherRecalc(true);}catch(_e){}
}
function samaEntryEnsureEditButton(){
  const title=String(window.mTitle?.innerText||document.getElementById('mTitle')?.innerText||'').toLocaleUpperCase('tr-TR');
  if(!title.includes('GİRİŞ /')&&!title.includes('GIRIS /'))return;
  const modalEl=document.getElementById('modal')||window.modal;
  const completed=Number(window.cx?.entry_done||0)===1;
  const unlocked=modalEl?.dataset?.samaEntryUnlocked==='1';

  if(!completed){
    if(modalEl)modalEl.dataset.samaEntryUnlocked='1';
    samaEntrySetEditable(true);
    if(window.mSave){mSave.disabled=false;mSave.style.opacity='1';mSave.style.pointerEvents='auto';}
    try{if(typeof entryOtherRecalc==='function')entryOtherRecalc(true);}catch(_e){}
    return;
  }

  if(!unlocked){
    samaEntrySetEditable(false);
    if(window.mSave){mSave.disabled=true;mSave.style.opacity='.45';mSave.style.pointerEvents='none';}
  }else{
    samaEntrySetEditable(true);
    if(window.mSave){mSave.disabled=false;mSave.style.opacity='1';mSave.style.pointerEvents='auto';}
  }

  const save=window.mSave||document.getElementById('mSave');
  if(save && !document.getElementById('samaEntryEditBtn') && samaEntryCanEdit()){
    const btn=document.createElement('button');
    btn.id='samaEntryEditBtn';btn.type='button';btn.className='btn secondary';
    btn.textContent=unlocked?'DÜZELTME MODU AÇIK':'DÜZELT';
    btn.style.marginRight='8px';
    btn.onclick=samaEntryUnlockEdit;
    if(unlocked){btn.disabled=true;btn.style.opacity='.75';}
    save.parentElement?.insertBefore(btn,save);
  }

  const body=window.mBody||document.getElementById('mBody');
  if(body && !document.getElementById('samaEntryEditInfo')){
    const info=document.createElement('div');
    info.id='samaEntryEditInfo';info.className='calc';
    info.style.cssText='margin:0 0 10px;border-color:#f59e0b;background:#fffbeb';
    info.innerHTML=unlocked?'<b>DÜZELTME MODU AÇIK.</b>':'<b>KAYITLI GİRİŞ.</b> Kontrol modundasınız. Değişiklik için DÜZELT butonuna basın.';
    body.prepend(info);
  }

  if(save && !save.dataset.samaEntryWrapped && typeof save.onclick==='function'){
    const original=save.onclick;
    save.onclick=async function(ev){
      if(Number(window.cx?.entry_done||0)===1 && (modalEl?.dataset?.samaEntryUnlocked!=='1'))return;
      await samaEntryFlushExtrasAsync();
      return await original.call(this,ev);
    };
    save.dataset.samaEntryWrapped='1';
  }
}
function samaEntryEditBoot(){
  setInterval(()=>{
    try{samaEntryEnsureEditButton();}catch(_e){}
  },250);
}

function entryOtherRecalc(runCalc=true){
  if(typeof calcEntry==='function')calcEntry();
  if(typeof fixedEntryRefreshSummary==='function')fixedEntryRefreshSummary();
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',samaEntryEditBoot);else samaEntryEditBoot();
'''

marker = 'async function kbLoadSingleV2(){'
inserted = False
if marker in html and 'function samaEntryUnlockEdit' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)
    inserted = True

core.HTML = html
print(f'[SAMA] Entry OTHER live + completed Entry DÜZELT unlock active: js={1 if inserted else 0}')

# Final expense integrity layer runs after this usability layer has finished modifying core.HTML.
import entry_fixed_other_kolaybi_final_patch as entry_fixed_other_kolaybi_final

# The operator also confirmed a separate 15,000 IQD taxi expense for SCNA 95621.
import entry_95621_taxi_recovery_patch as entry_95621_taxi_recovery

# Final UI layers: monetary Edit Center + immediate permanent purge from recycle list.
import deleted_trip_purge_patch as deleted_trip_purge
