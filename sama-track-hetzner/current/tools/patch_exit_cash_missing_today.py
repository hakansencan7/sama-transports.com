from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_EXIT_CASH_MISSING_FROM_20260830_V1'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

backend=r'''

# SAMA_EXIT_CASH_MISSING_FROM_20260830_V1
class ExitCashSetIn(BaseModel):
    amount: float = 0

@app.get('/api/exit-cash-missing')
def exit_cash_missing():
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name,
             t.trip_date,t.exit_at,t.created_at,t.exit_allowance,t.exit_premium,t.exit_other,
             t.exit_cash,t.exit_done,t.status
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      WHERE t.exit_done=1
        AND COALESCE(t.is_deleted,0)=0
        AND COALESCE(t.exit_cash,0)<=0
        AND DATE(COALESCE(NULLIF(t.exit_at,''),NULLIF(t.trip_date,''),NULLIF(t.created_at,'')))>=DATE('2026-08-30')
      ORDER BY DATE(COALESCE(NULLIF(t.exit_at,''),NULLIF(t.trip_date,''),NULLIF(t.created_at,''))) DESC,t.id DESC
    """)]
    c.close(); return rows

@app.post('/api/trips/{scna}/exit-cash')
def set_trip_exit_cash(scna:str,x:ExitCashSetIn):
    amount=float(x.amount or 0)
    if amount<=0:
        raise HTTPException(400,'Çıkışta şoföre verilen toplam nakit 0 dan büyük olmalı.')
    key=_normalize_scna_value(scna)
    c=db()
    row=c.execute("SELECT scna,exit_done,exit_cash FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) AND COALESCE(is_deleted,0)=0 LIMIT 1",(key,)).fetchone()
    if not row:
        c.close(); raise HTTPException(404,'SCNA bulunamadı.')
    if int(row['exit_done'] or 0)!=1:
        c.close(); raise HTTPException(400,'Bu sevkiyatın çıkış işlemi tamamlanmamış.')
    c.execute("UPDATE trips SET exit_cash=?,updated_at=CURRENT_TIMESTAMP WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))",(amount,key))
    c.commit(); c.close()
    audit('EXIT_CASH_SET',key,f'Çıkışta şoföre verilen toplam nakit: {amount:g} IQD','SEVKIYAT')
    return {'ok':True,'scna':key,'exit_cash':amount}
'''
anchor="@app.get('/api/cash-out-diagnostic/{scna}')"
i=s.find(anchor)
if i<0: raise RuntimeError('backend anchor not found')
s=s[:i]+backend+'\n'+s[i:]

old='''<span class="section-note">Çıkış bekleyen kayıtlar varsayılan gelir.</span>\n</div>\n<div class="table">'''
new='''<span class="section-note">Çıkış bekleyen kayıtlar varsayılan gelir.</span>\n</div>\n<div id="exitCashMissingBox" class="calc" style="display:none;border-color:#f59e0b;background:#fffbeb;margin-bottom:14px"></div>\n<div class="table">'''
if old not in s: raise RuntimeError('exit html anchor not found')
s=s.replace(old,new,1)

old_func='''async function loadExit(){\n  const status=exitStatusFilter.value||'Bekliyor';'''
new_func='''async function loadExit(){\n  await loadExitCashMissing();\n  const status=exitStatusFilter.value||'Bekliyor';'''
if old_func not in s: raise RuntimeError('loadExit anchor not found')
s=s.replace(old_func,new_func,1)

js=r'''

async function loadExitCashMissing(){
  const box=document.getElementById('exitCashMissingBox');
  if(!box)return;
  try{
    const rows=await api('/api/exit-cash-missing');
    if(!rows.length){box.style.display='none';box.innerHTML='';return;}
    box.style.display='block';
    box.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px">
      <div><b style="color:#92400e">⚠ ÇIKIŞ PARASI EKSİK</b><br><span class="small">30.08.2026 ve sonrası çıkışı tamamlanmış fakat şoföre verilen toplam nakit girilmemiş ${rows.length} kayıt.</span></div>
      <span class="badge warn">${rows.length} KAYIT</span>
    </div>
    <div class="table"><table class="mini"><thead><tr><th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>ÇIKIŞ TARİHİ</th><th>HARCIRAH</th><th>PRİM</th><th>OTHER</th><th>ŞOFÖRE VERİLEN TOPLAM NAKİT</th><th>İŞLEM</th></tr></thead><tbody>
    ${rows.map(x=>`<tr class="alert-orange"><td><b>${x.scna}</b></td><td>${x.plate||''}</td><td>${x.driver_name||''}</td><td>${fmtDateTime(x.exit_at||x.trip_date||x.created_at)}</td><td>${money(x.exit_allowance||0)}</td><td>${money(x.exit_premium||0)}</td><td>${money(x.exit_other||0)}</td><td><input id="missingCash_${String(x.scna).replace(/[^A-Za-z0-9_]/g,'_')}" type="text" inputmode="decimal" placeholder="Toplam IQD" style="width:150px"></td><td><button class="btn orange" onclick="saveMissingExitCash('${String(x.scna).replace(/'/g,"\\'")}')">Kaydet</button></td></tr>`).join('')}
    </tbody></table></div>`;
  }catch(e){
    box.style.display='block';box.innerHTML='<b style="color:#991b1b">Çıkış parası eksik kayıtlar yüklenemedi: '+e.message+'</b>';
  }
}

async function saveMissingExitCash(scna){
  const id='missingCash_'+String(scna).replace(/[^A-Za-z0-9_]/g,'_');
  const el=document.getElementById(id);
  const amount=Number(String(el?.value||'').replace(/\./g,'').replace(',','.'));
  if(!amount||amount<=0){alert('Şoföre verilen toplam nakdi girin.');return;}
  if(!confirm(scna+' için şoföre verilen toplam nakit '+money(amount)+' IQD olarak kaydedilsin mi?'))return;
  try{
    await api('/api/trips/'+encodeURIComponent(scna)+'/exit-cash',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})});
    await loadExitCashMissing();
    if(typeof loadCashControl==='function'){
      try{await loadCashControl();}catch(e){}
    }
  }catch(e){alert(e.message);}
}
'''
anchor_js='async function loadExit(){'
i=s.find(anchor_js)
if i<0: raise RuntimeError('js insert anchor not found')
s=s[:i]+js+'\n'+s[i:]

p.write_text(s,encoding='utf-8')
print('patched exit cash missing from 2026-08-30')
