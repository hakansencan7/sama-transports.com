from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_CASH_DIAGNOSTIC_V1'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

BACKEND=r'''

# SAMA_CASH_DIAGNOSTIC_V1
@app.get('/api/cash-diagnostic/{scna}')
def cash_diagnostic(scna:str):
    key=_normalize_scna_value(scna)
    c=db()
    row=c.execute("""
      SELECT t.*,
             COALESCE(d.name,'') driver_name,
             COALESCE(a.name,'') area_name,
             COALESCE(cu.name,'') customer_name
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      LEFT JOIN areas a ON a.id=t.area_id
      LEFT JOIN customers cu ON cu.id=t.customer_id
      WHERE UPPER(TRIM(t.scna))=UPPER(TRIM(?))
      LIMIT 1
    """,(key,)).fetchone()
    if not row:
        c.close(); raise HTTPException(404,'SCNA bulunamadı.')
    x=dict(row)
    effective_exit=x.get('exit_at') or x.get('trip_date') or x.get('created_at') or ''
    reasons=[]
    if float(x.get('exit_cash') or 0)<=0: reasons.append('exit_cash 0 veya boş')
    if int(x.get('exit_done') or 0)!=1: reasons.append('exit_done 1 değil')
    if int(x.get('is_deleted') or 0)==1: reasons.append('kayıt silinmiş')
    if not effective_exit: reasons.append('çıkış tarihi bulunamadı')
    result={
      'scna':x.get('scna'),'plate':x.get('plate'),'driver_name':x.get('driver_name'),
      'trip_date':x.get('trip_date'),'exit_cash':x.get('exit_cash'),'exit_done':x.get('exit_done'),
      'exit_at':x.get('exit_at'),'created_at':x.get('created_at'),'updated_at':x.get('updated_at'),
      'effective_exit_date':effective_exit,'is_deleted':x.get('is_deleted',0),
      'exit_allowance':x.get('exit_allowance'),'exit_premium':x.get('exit_premium'),
      'exit_other':x.get('exit_other'),'dock_fee':x.get('dock_fee'),'port_fee':x.get('port_fee'),
      'sonar':x.get('sonar'),'entry_cash_handed':x.get('entry_cash_handed'),
      'entry_collection':x.get('entry_collection'),'entry_done':x.get('entry_done'),'entry_at':x.get('entry_at'),
      'cash_out_eligible':len(reasons)==0,'cash_out_block_reasons':reasons
    }
    c.close(); return result
'''
anchor="@app.post('/api/cash-control/expense')"
idx=s.find(anchor)
if idx<0: raise RuntimeError('cash control anchor missing')
s=s[:idx]+BACKEND+'\n'+s[idx:]

OLD='<div class="filterbar"><b>Günlük Kasa Kontrolü</b>'
NEW='<div class="filterbar"><b>Günlük Kasa Kontrolü</b><input id="cashDiagScna" placeholder="SCNA Tanı" style="max-width:150px"><button class="btn secondary" onclick="openCashDiagnostic()">SCNA Kasa Tanı</button>'
if OLD not in s: raise RuntimeError('cash filterbar anchor missing')
s=s.replace(OLD,NEW,1)

JS=r'''
function openCashDiagnostic(){
 const scna=(document.getElementById('cashDiagScna')?.value||'').trim();
 if(!scna)return alert('SCNA girin.');
 api('/api/cash-diagnostic/'+encodeURIComponent(scna)).then(x=>{
   const reasons=(x.cash_out_block_reasons||[]).length?(x.cash_out_block_reasons||[]).join(', '):'Yok';
   openM('SCNA Kasa Tanı — '+(x.scna||scna),`<div class="table"><table><tbody>
   <tr><th>SCNA</th><td>${x.scna||''}</td></tr><tr><th>Plaka</th><td>${x.plate||''}</td></tr><tr><th>Şoför</th><td>${x.driver_name||''}</td></tr>
   <tr><th>exit_cash</th><td><b>${money(x.exit_cash||0)} IQD</b></td></tr><tr><th>exit_done</th><td>${x.exit_done}</td></tr>
   <tr><th>exit_at</th><td>${fmtDateTime(x.exit_at)}</td></tr><tr><th>trip_date</th><td>${x.trip_date||''}</td></tr><tr><th>created_at</th><td>${fmtDateTime(x.created_at)}</td></tr>
   <tr><th>Efektif Çıkış Tarihi</th><td>${fmtDateTime(x.effective_exit_date)}</td></tr><tr><th>Silinmiş</th><td>${x.is_deleted||0}</td></tr>
   <tr><th>Harcırah</th><td>${money(x.exit_allowance||0)}</td></tr><tr><th>Prim</th><td>${money(x.exit_premium||0)}</td></tr><tr><th>Other</th><td>${money(x.exit_other||0)}</td></tr>
   <tr><th>Kasa Çıkışına Uygun</th><td><b>${x.cash_out_eligible?'EVET':'HAYIR'}</b></td></tr><tr><th>Engel Nedeni</th><td>${reasons}</td></tr>
   </tbody></table></div>`,null);
 }).catch(e=>alert(e.message));
}
'''
anchor_js='function openShipmentCashOutDetails(){'
idx=s.find(anchor_js)
if idx<0: raise RuntimeError('cash diagnostic JS anchor missing')
s=s[:idx]+JS+'\n'+s[idx:]

p.write_text(s,encoding='utf-8')
print('patched cash diagnostic')
