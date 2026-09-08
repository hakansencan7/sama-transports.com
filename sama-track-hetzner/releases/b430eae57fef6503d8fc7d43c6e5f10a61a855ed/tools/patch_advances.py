from pathlib import Path

p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_ADVANCE_TRACKING_V1'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

BACKEND=r'''
# SAMA_ADVANCE_TRACKING_V1
class AdvanceIn(BaseModel):
    recipient_type: str = 'USTA'
    recipient_name: str = ''
    plate: str = ''
    scna: str = ''
    purpose: str = ''
    amount: float = 0
    currency: str = 'IQD'
    note: str = ''

class AdvanceSettlementIn(BaseModel):
    settlement_type: str = 'FATURA'
    amount: float = 0
    document_no: str = ''
    note: str = ''

class AdvanceUpdateIn(BaseModel):
    recipient_type: str = 'USTA'
    recipient_name: str = ''
    plate: str = ''
    scna: str = ''
    purpose: str = ''
    amount: float = 0
    currency: str = 'IQD'
    note: str = ''


def _ensure_advances(c):
    c.execute("""CREATE TABLE IF NOT EXISTS cash_advances(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      recipient_type TEXT NOT NULL DEFAULT 'USTA',
      recipient_name TEXT NOT NULL DEFAULT '',
      plate TEXT DEFAULT '',
      scna TEXT DEFAULT '',
      purpose TEXT DEFAULT '',
      amount REAL NOT NULL DEFAULT 0,
      settled_amount REAL NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT 'IQD',
      note TEXT DEFAULT '',
      status TEXT NOT NULL DEFAULT 'ACIK',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      created_by TEXT DEFAULT '',
      updated_at DATETIME,
      updated_by TEXT DEFAULT ''
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cash_advance_settlements(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      advance_id INTEGER NOT NULL,
      settlement_type TEXT NOT NULL DEFAULT 'FATURA',
      amount REAL NOT NULL DEFAULT 0,
      document_no TEXT DEFAULT '',
      note TEXT DEFAULT '',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      created_by TEXT DEFAULT ''
    )""")
    c.commit()

@app.get('/api/advances')
def advances_list(status:str=''):
    c=db(); _ensure_advances(c)
    sql="""SELECT a.*,MAX(0,a.amount-a.settled_amount) remaining
      FROM cash_advances a WHERE 1=1"""
    par=[]
    if status: sql+=' AND a.status=?'; par.append(status.upper())
    sql+=' ORDER BY CASE WHEN a.status=\'ACIK\' THEN 0 WHEN a.status=\'KISMI\' THEN 1 ELSE 2 END,a.id DESC LIMIT 2000'
    rows=[dict(r) for r in c.execute(sql,par)]
    c.close(); return rows

@app.post('/api/advances')
def advances_create(x:AdvanceIn):
    typ=(x.recipient_type or 'USTA').strip().upper()
    name=(x.recipient_name or '').strip()
    amount=float(x.amount or 0); cur=(x.currency or 'IQD').strip().upper()
    if typ not in ('SOFOR','USTA','PERSONEL','DIGER'): raise HTTPException(400,'Geçersiz alıcı tipi.')
    if not name: raise HTTPException(400,'Ad Soyad / kişi adı zorunlu.')
    if amount<=0: raise HTTPException(400,'Tutar 0 dan büyük olmalı.')
    if not (x.purpose or '').strip(): raise HTTPException(400,'Avans nedeni / iş açıklaması zorunlu.')
    c=db(); _ensure_advances(c)
    user=CURRENT_AUTH_USER.get() or {}; username=user.get('username','') if isinstance(user,dict) else ''
    c.execute("""INSERT INTO cash_advances(recipient_type,recipient_name,plate,scna,purpose,amount,currency,note,status,created_at,created_by)
      VALUES(?,?,?,?,?,?,?,?,'ACIK',DATETIME('now','localtime'),?)""",
      (typ,name,(x.plate or '').strip().upper(),(x.scna or '').strip().upper(),(x.purpose or '').strip(),amount,cur,(x.note or '').strip(),username))
    aid=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.commit(); c.close()
    audit('ADVANCE_CREATE',str(aid),f'{typ} {name} {amount:g} {cur} - {(x.purpose or "").strip()}','AVANS')
    return {'ok':True,'id':aid}

@app.post('/api/advances/{advance_id}/settlement')
def advances_settlement(advance_id:int,x:AdvanceSettlementIn):
    st=(x.settlement_type or 'FATURA').strip().upper(); amt=float(x.amount or 0)
    if st not in ('FATURA','FIS','NAKIT_IADE','MAHSUP'): raise HTTPException(400,'Geçersiz kapatma türü.')
    if amt<=0: raise HTTPException(400,'Tutar 0 dan büyük olmalı.')
    c=db(); _ensure_advances(c)
    row=c.execute('SELECT * FROM cash_advances WHERE id=?',(advance_id,)).fetchone()
    if not row: c.close(); raise HTTPException(404,'Avans kaydı bulunamadı.')
    remaining=max(0,float(row['amount'] or 0)-float(row['settled_amount'] or 0))
    if amt>remaining+0.0001: c.close(); raise HTTPException(400,f'Girilen tutar kalan avansı aşamaz. Kalan: {remaining:g}')
    user=CURRENT_AUTH_USER.get() or {}; username=user.get('username','') if isinstance(user,dict) else ''
    newsettled=float(row['settled_amount'] or 0)+amt
    status='KAPANDI' if newsettled>=float(row['amount'] or 0)-0.0001 else 'KISMI'
    c.execute("""INSERT INTO cash_advance_settlements(advance_id,settlement_type,amount,document_no,note,created_at,created_by)
      VALUES(?,?,?,?,?,DATETIME('now','localtime'),?)""",(advance_id,st,amt,(x.document_no or '').strip(),(x.note or '').strip(),username))
    c.execute("UPDATE cash_advances SET settled_amount=?,status=?,updated_at=DATETIME('now','localtime'),updated_by=? WHERE id=?",(newsettled,status,username,advance_id))
    c.commit(); c.close()
    audit('ADVANCE_SETTLEMENT',str(advance_id),f'{st} {amt:g}','AVANS')
    return {'ok':True,'status':status,'settled_amount':newsettled,'remaining':max(0,float(row['amount'] or 0)-newsettled)}

@app.post('/api/advances/{advance_id}/update')
def advances_update(advance_id:int,x:AdvanceUpdateIn):
    amount=float(x.amount or 0)
    if amount<=0: raise HTTPException(400,'Tutar 0 dan büyük olmalı.')
    if not (x.recipient_name or '').strip(): raise HTTPException(400,'Kişi adı zorunlu.')
    if not (x.purpose or '').strip(): raise HTTPException(400,'Avans nedeni zorunlu.')
    c=db(); _ensure_advances(c)
    row=c.execute('SELECT * FROM cash_advances WHERE id=?',(advance_id,)).fetchone()
    if not row: c.close(); raise HTTPException(404,'Avans kaydı bulunamadı.')
    if amount < float(row['settled_amount'] or 0): c.close(); raise HTTPException(400,'Yeni tutar belgelenmiş/iadeli tutardan küçük olamaz.')
    user=CURRENT_AUTH_USER.get() or {}; username=user.get('username','') if isinstance(user,dict) else ''
    status='KAPANDI' if float(row['settled_amount'] or 0)>=amount-0.0001 else ('KISMI' if float(row['settled_amount'] or 0)>0 else 'ACIK')
    c.execute("""UPDATE cash_advances SET recipient_type=?,recipient_name=?,plate=?,scna=?,purpose=?,amount=?,currency=?,note=?,status=?,updated_at=DATETIME('now','localtime'),updated_by=? WHERE id=?""",
      ((x.recipient_type or 'USTA').strip().upper(),(x.recipient_name or '').strip(),(x.plate or '').strip().upper(),(x.scna or '').strip().upper(),(x.purpose or '').strip(),amount,(x.currency or 'IQD').strip().upper(),(x.note or '').strip(),status,username,advance_id))
    c.commit(); c.close(); audit('ADVANCE_UPDATE',str(advance_id),'Avans kaydı düzeltildi','AVANS')
    return {'ok':True,'status':status}

@app.get('/api/advances/{advance_id}/settlements')
def advances_settlements(advance_id:int):
    c=db(); _ensure_advances(c)
    rows=[dict(r) for r in c.execute('SELECT * FROM cash_advance_settlements WHERE advance_id=? ORDER BY id DESC',(advance_id,))]
    c.close(); return rows
'''

idx=s.find('\n\nHTML = r"""')
if idx<0: raise RuntimeError('HTML anchor not found')
s=s[:idx]+BACKEND+s[idx:]

needle="    <button onclick=\"show('deleted',this)\">Silinenler</button>"
nav="    <button onclick=\"show('advances',this)\">Avans Takip</button>\n"+needle
if needle not in s: raise RuntimeError('management nav anchor not found')
s=s.replace(needle,nav,1)

PANEL=r'''
<section id="advances" class="panel">
<div class="filterbar"><b>Avans Takip</b><input id="advQ" class="grow" placeholder="Kişi / plaka / iş / SCNA ara" oninput="renderAdvances()"><select id="advType" onchange="renderAdvances()"><option value="">Tüm Kişiler</option><option value="USTA">Usta</option><option value="SOFOR">Şoför</option><option value="PERSONEL">Personel</option><option value="DIGER">Diğer</option></select><select id="advStatus" onchange="renderAdvances()"><option value="">Tüm Durumlar</option><option value="ACIK">Açık</option><option value="KISMI">Kısmi</option><option value="KAPANDI">Kapandı</option></select><button class="btn primary" onclick="openAdvanceNew()">+ Yeni Avans</button><button class="btn secondary" onclick="loadAdvances()">Yenile</button></div>
<div class="cards"><div class="card">Açık Kayıt<b id="advOpen">0</b></div><div class="card">Toplam Verilen<b id="advTotal">0</b></div><div class="card">Belgelenen / İade<b id="advSettled">0</b></div><div class="card">Kalan Açık Bakiye<b id="advRemaining">0</b></div></div>
<div class="table"><table><thead><tr><th>TARİH</th><th>TİP</th><th>KİŞİ</th><th>PLAKA</th><th>SCNA</th><th>İŞ / NEDEN</th><th>VERİLEN</th><th>BELGELENEN/İADE</th><th>KALAN</th><th>PARA</th><th>NOT</th><th>DURUM</th><th>İŞLEM</th></tr></thead><tbody id="advRows"></tbody></table></div>
</section>
'''
needle='<section id="deleted" class="panel">'
if needle not in s: raise RuntimeError('deleted panel anchor not found')
s=s.replace(needle,PANEL+'\n'+needle,1)

s=s.replace("audit:'audit.view',useradmin:'users.manage',deleted:'shipment.delete'","audit:'audit.view',useradmin:'users.manage',deleted:'shipment.delete',advances:'users.manage'",1)
s=s.replace("  if(id==='useradmin') loadAuthUsers();","  if(id==='useradmin') loadAuthUsers();\n  if(id==='advances') loadAdvances();",1)

JS=r'''
let advanceRows=[];
function advTypeLabel(t){return {USTA:'USTA',SOFOR:'ŞOFÖR',PERSONEL:'PERSONEL',DIGER:'DİĞER'}[t]||t||'';}
async function loadAdvances(){advanceRows=await api('/api/advances');renderAdvances();}
function renderAdvances(){
 const q=(document.getElementById('advQ')?.value||'').toLocaleUpperCase('tr-TR'),typ=document.getElementById('advType')?.value||'',st=document.getElementById('advStatus')?.value||'';
 const rows=advanceRows.filter(x=>(!typ||x.recipient_type===typ)&&(!st||x.status===st)&&(!q||[x.recipient_name,x.plate,x.scna,x.purpose,x.note].join(' ').toLocaleUpperCase('tr-TR').includes(q)));
 advRows.innerHTML=rows.map(x=>`<tr><td>${fmtDateTime(x.created_at)}</td><td>${advTypeLabel(x.recipient_type)}</td><td><b>${x.recipient_name||''}</b></td><td>${x.plate||''}</td><td>${x.scna||''}</td><td>${x.purpose||''}</td><td>${money(x.amount)}</td><td>${money(x.settled_amount)}</td><td><b>${money(x.remaining)}</b></td><td>${x.currency||''}</td><td>${x.note||''}</td><td>${x.status||''}</td><td><div class="compact-actions"><button class="btn green" onclick="openAdvanceSettlement(${x.id})">FATURA / FİŞ / İADE</button><button class="btn secondary" onclick="openAdvanceHistory(${x.id})">GEÇMİŞ</button><button class="btn secondary" onclick="editAdvance(${x.id})">DÜZENLE</button></div></td></tr>`).join('');
 const open=advanceRows.filter(x=>x.status!=='KAPANDI'); advOpen.innerText=open.length; advTotal.innerText=money(advanceRows.reduce((a,x)=>a+Number(x.amount||0),0)); advSettled.innerText=money(advanceRows.reduce((a,x)=>a+Number(x.settled_amount||0),0)); advRemaining.innerText=money(open.reduce((a,x)=>a+Number(x.remaining||0),0));
 if(typeof v54InitTables==='function')v54InitTables();
}
function openAdvanceNew(){openM('Yeni Avans',`<div class="grid"><div class="field"><label>Alıcı Tipi</label><select id="aType"><option value="USTA">Usta</option><option value="SOFOR">Şoför</option><option value="PERSONEL">Personel</option><option value="DIGER">Diğer</option></select></div><div class="field"><label>Ad Soyad / Kişi</label><input id="aName"></div><div class="field"><label>Plaka (opsiyonel)</label><input id="aPlate"></div><div class="field"><label>SCNA (opsiyonel)</label><input id="aScna"></div><div class="field"><label>Tutar</label><input id="aAmount" type="number" min="0" step="1"></div><div class="field"><label>Para Birimi</label><select id="aCurrency"><option>IQD</option><option>USD</option><option>TRY</option></select></div><div class="field wide"><label>İş / Avans Nedeni</label><input id="aPurpose" placeholder="Örn: 22L29155 fren tamiri için parça ve işçilik"></div><div class="field wide"><label>Not</label><textarea id="aNote"></textarea></div></div>`,async()=>{try{await api('/api/advances',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({recipient_type:aType.value,recipient_name:aName.value,plate:aPlate.value,scna:aScna.value,purpose:aPurpose.value,amount:Number(aAmount.value||0),currency:aCurrency.value,note:aNote.value})});closeM();await loadAdvances();alert('Avans kaydedildi.');}catch(e){alert(e.message);}});}
function openAdvanceSettlement(id){const x=advanceRows.find(r=>Number(r.id)===Number(id));if(!x)return;openM(`${x.recipient_name} — Avans Kapatma`,`<div class="calc"><b>Verilen:</b> ${money(x.amount)} ${x.currency}<br><b>Belgelenen/İade:</b> ${money(x.settled_amount)} ${x.currency}<br><b>Kalan:</b> ${money(x.remaining)} ${x.currency}</div><div class="grid" style="margin-top:12px"><div class="field"><label>İşlem Türü</label><select id="asType"><option value="FATURA">Fatura</option><option value="FIS">Fiş</option><option value="NAKIT_IADE">Nakit İade</option><option value="MAHSUP">Mahsup</option></select></div><div class="field"><label>Tutar</label><input id="asAmount" type="number" min="0" step="1"></div><div class="field"><label>Belge No</label><input id="asDoc"></div><div class="field wide"><label>Açıklama</label><textarea id="asNote"></textarea></div></div>`,async()=>{try{await api('/api/advances/'+id+'/settlement',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({settlement_type:asType.value,amount:Number(asAmount.value||0),document_no:asDoc.value,note:asNote.value})});closeM();await loadAdvances();alert('Avans hareketi işlendi.');}catch(e){alert(e.message);}});}
async function openAdvanceHistory(id){const rows=await api('/api/advances/'+id+'/settlements');const x=advanceRows.find(r=>Number(r.id)===Number(id));openM(`${x?.recipient_name||''} — Avans Geçmişi`,`<div class="table"><table><thead><tr><th>TARİH</th><th>TÜR</th><th>TUTAR</th><th>BELGE NO</th><th>AÇIKLAMA</th><th>GİREN</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${fmtDateTime(r.created_at)}</td><td>${r.settlement_type}</td><td>${money(r.amount)} ${x?.currency||''}</td><td>${r.document_no||''}</td><td>${r.note||''}</td><td>${r.created_by||''}</td></tr>`).join('')}</tbody></table></div>`,()=>closeM());}
function editAdvance(id){const x=advanceRows.find(r=>Number(r.id)===Number(id));if(!x)return;openM(`${x.recipient_name} — Avansı Düzelt`,`<div class="grid"><div class="field"><label>Alıcı Tipi</label><select id="aeType"><option value="USTA">Usta</option><option value="SOFOR">Şoför</option><option value="PERSONEL">Personel</option><option value="DIGER">Diğer</option></select></div><div class="field"><label>Ad Soyad / Kişi</label><input id="aeName" value="${x.recipient_name||''}"></div><div class="field"><label>Plaka</label><input id="aePlate" value="${x.plate||''}"></div><div class="field"><label>SCNA</label><input id="aeScna" value="${x.scna||''}"></div><div class="field"><label>Tutar</label><input id="aeAmount" type="number" value="${Number(x.amount||0)}"></div><div class="field"><label>Para Birimi</label><select id="aeCurrency"><option>IQD</option><option>USD</option><option>TRY</option></select></div><div class="field wide"><label>İş / Avans Nedeni</label><input id="aePurpose" value="${String(x.purpose||'').replace(/\"/g,'&quot;')}"></div><div class="field wide"><label>Not</label><textarea id="aeNote">${x.note||''}</textarea></div></div>`,async()=>{try{await api('/api/advances/'+id+'/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({recipient_type:aeType.value,recipient_name:aeName.value,plate:aePlate.value,scna:aeScna.value,purpose:aePurpose.value,amount:Number(aeAmount.value||0),currency:aeCurrency.value,note:aeNote.value})});closeM();await loadAdvances();alert('Avans kaydı güncellendi.');}catch(e){alert(e.message);}});setTimeout(()=>{aeType.value=x.recipient_type||'USTA';aeCurrency.value=x.currency||'IQD';},0);}
'''

idx=s.find('\nasync function loadDeletedTrips')
if idx<0: raise RuntimeError('JS anchor not found')
s=s[:idx]+JS+s[idx:]

p.write_text(s,encoding='utf-8')
print('advance tracking patched')
