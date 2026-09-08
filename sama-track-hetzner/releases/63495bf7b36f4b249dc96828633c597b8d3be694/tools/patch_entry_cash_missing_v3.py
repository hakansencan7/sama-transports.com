from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_ENTRY_CASH_MISSING_V3'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

# 1) Improve effective entry date order: entry_at -> delivery_time -> updated_at -> trip_date -> created_at.
s=s.replace("COALESCE(NULLIF(entry_at,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')) entry_date",
            "COALESCE(NULLIF(entry_at,''),NULLIF(delivery_time,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')) entry_date")
s=s.replace("DATE(COALESCE(NULLIF(entry_at,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')))=?",
            "DATE(COALESCE(NULLIF(entry_at,''),NULLIF(delivery_time,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')))=?")
s=s.replace("ORDER BY COALESCE(NULLIF(entry_at,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')) DESC,scna",
            "ORDER BY COALESCE(NULLIF(entry_at,''),NULLIF(delivery_time,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')) DESC,scna")
s=s.replace("effective_entry=x.get('entry_at') or x.get('updated_at') or x.get('trip_date') or x.get('created_at') or None",
            "effective_entry=x.get('entry_at') or x.get('delivery_time') or x.get('updated_at') or x.get('trip_date') or x.get('created_at') or None")

anchor="# SAMA_EXIT_CASH_MISSING_FROM_20260830_V1"
backend=r'''# SAMA_ENTRY_CASH_MISSING_V3
class EntryCashSetIn(BaseModel):
    amount: float = 0

@app.get('/api/entry-cash-missing')
def entry_cash_missing(business_date:str=''):
    day=(business_date or '').strip() or datetime.now().strftime('%Y-%m-%d')
    c=db()
    rows=[dict(r) for r in c.execute("""
      SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name,
             t.entry_cash_handed,t.entry_collection,t.entry_done,t.entry_at,t.delivery_time,t.trip_date,t.created_at,t.updated_at,t.status,
             COALESCE(NULLIF(t.entry_at,''),NULLIF(t.delivery_time,''),NULLIF(t.updated_at,''),NULLIF(t.trip_date,''),NULLIF(t.created_at,'')) effective_entry_date
      FROM trips t
      LEFT JOIN drivers d ON d.id=t.driver_id
      WHERE t.entry_done=1
        AND COALESCE(t.is_deleted,0)=0
        AND COALESCE(t.entry_cash_handed,0)<=0
        AND DATE(COALESCE(NULLIF(t.entry_at,''),NULLIF(t.delivery_time,''),NULLIF(t.updated_at,''),NULLIF(t.trip_date,''),NULLIF(t.created_at,'')))=?
      ORDER BY effective_entry_date DESC,t.scna
    """,(day,))]
    c.close(); return rows

@app.post('/api/trips/{scna}/entry-cash')
def set_entry_cash(scna:str,x:EntryCashSetIn):
    amount=float(x.amount or 0)
    if amount<=0:
        raise HTTPException(400,'Şoförün teslim ettiği para 0’dan büyük olmalı.')
    key=_normalize_scna_value(scna)
    c=db()
    row=c.execute("SELECT scna,entry_done FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) AND COALESCE(is_deleted,0)=0 LIMIT 1",(key,)).fetchone()
    if not row:
        c.close(); raise HTTPException(404,'SCNA bulunamadı.')
    if int(row['entry_done'] or 0)!=1:
        c.close(); raise HTTPException(409,'Sevkiyat girişi tamamlanmamış.')
    c.execute("UPDATE trips SET entry_cash_handed=?,updated_at=CURRENT_TIMESTAMP WHERE scna=?",(amount,row['scna']))
    c.commit(); c.close()
    audit('ENTRY_CASH_SET',row['scna'],f'Şoförün teslim ettiği para: {amount:.2f} IQD')
    return {'ok':True,'scna':row['scna'],'entry_cash_handed':amount}

'''+anchor
if anchor not in s:
    raise RuntimeError('backend anchor missing')
s=s.replace(anchor,backend,1)

# Add missing-cash panel into cash-control view near the diagnostic area if possible.
ui_anchor='''<button class="btn orange" onclick="openEntryCashDiagnostic()">Giriş / Muhasebe Tanı</button>'''
panel='''<button class="btn orange" onclick="openEntryCashDiagnostic()">Giriş / Muhasebe Tanı</button>
<button class="btn secondary" onclick="openEntryCashMissing()">Muhasebeye Düşmeyen Dönüşler</button>'''
if ui_anchor in s:
    s=s.replace(ui_anchor,panel,1)
else:
    print('warning: entry diagnostic button not found')

js_anchor='''function openEntryCashDiagnostic(){'''
js=r'''async function openEntryCashMissing(){
 const day=(document.getElementById('cashDate')?.value||new Date().toISOString().slice(0,10));
 try{
   const rows=await api('/api/entry-cash-missing?business_date='+encodeURIComponent(day));
   const body=(rows||[]).length ? (rows||[]).map(x=>`<tr>
     <td><b>${x.scna||''}</b></td><td>${x.plate||''}</td><td>${x.driver_name||''}</td>
     <td>${fmtDateTime(x.effective_entry_date)}</td><td>${money(x.entry_collection||0)} IQD</td>
     <td><input id="ecm_${x.scna}" type="text" inputmode="decimal" placeholder="Teslim edilen para" style="min-width:150px"></td>
     <td><button class="btn green" onclick="saveMissingEntryCash('${x.scna}')">Kaydet</button></td>
   </tr>`).join('') : '<tr><td colspan="7">Bu tarihte muhasebeye düşmeyen tamamlanmış dönüş yok.</td></tr>';
   openM('Muhasebeye Düşmeyen Dönüşler — '+day,`<div class="small" style="margin-bottom:10px">Girişi tamamlanmış ama “Şoförün Teslim Ettiği Para” 0/boş olan kayıtlar.</div><div class="table"><table><thead><tr><th>SCNA</th><th>Plaka</th><th>Şoför</th><th>Giriş Tarihi</th><th>Müşteriden Alınan</th><th>Şoförün Teslim Ettiği</th><th>İşlem</th></tr></thead><tbody>${body}</tbody></table></div>`,null);
 }catch(e){alert(e.message)}
}

async function saveMissingEntryCash(scna){
 const el=document.getElementById('ecm_'+scna);
 const amount=parseMoney(el?.value||0);
 if(!(amount>0))return alert('Teslim edilen para 0’dan büyük olmalı.');
 if(!confirm(scna+' için '+money(amount)+' IQD teslim edilen para olarak kaydedilsin mi?'))return;
 try{
   await api('/api/trips/'+encodeURIComponent(scna)+'/entry-cash',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})});
   alert('Kaydedildi. Günlük Kasa otomatik güncellenecek.');
   closeM();
   if(typeof loadCashControl==='function')await loadCashControl();
 }catch(e){alert(e.message)}
}

function openEntryCashDiagnostic(){'''
if js_anchor not in s:
    raise RuntimeError('JS anchor missing')
s=s.replace(js_anchor,js,1)

p.write_text(s,encoding='utf-8')
print('patched entry cash missing v3')
