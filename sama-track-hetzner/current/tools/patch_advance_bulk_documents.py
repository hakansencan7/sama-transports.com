from pathlib import Path

p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='// SAMA_ADVANCE_BULK_DOCUMENTS_V1'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

backend_anchor="""class AdvanceUpdateIn(BaseModel):
    recipient_type: str = 'USTA'
    recipient_name: str = ''
    plate: str = ''
    scna: str = ''
    purpose: str = ''
    amount: float = 0
    currency: str = 'IQD'
    note: str = ''
"""
backend_insert=backend_anchor+"""

class AdvanceBulkSettlementItem(BaseModel):
    settlement_type: str = 'FIS'
    amount: float = 0
    document_no: str = ''
    note: str = ''
    document_date: str = ''

class AdvanceBulkSettlementIn(BaseModel):
    items: list[AdvanceBulkSettlementItem] = []
"""
if backend_anchor not in s:
    raise RuntimeError('backend model anchor not found')
s=s.replace(backend_anchor,backend_insert,1)

endpoint_anchor="""@app.get('/api/advances/{advance_id}/settlements')
def advances_settlements(advance_id:int):
    c=db(); _ensure_advances(c)
    rows=[dict(r) for r in c.execute('SELECT * FROM cash_advance_settlements WHERE advance_id=? ORDER BY id DESC',(advance_id,))]
    c.close(); return rows
"""
endpoint_insert="""@app.post('/api/advances/{advance_id}/settlements/bulk')
def advances_settlements_bulk(advance_id:int,x:AdvanceBulkSettlementIn):
    items=x.items or []
    if not items: raise HTTPException(400,'En az bir belge satırı girilmeli.')
    if len(items)>200: raise HTTPException(400,'Tek seferde en fazla 200 belge girilebilir.')
    c=db(); _ensure_advances(c)
    row=c.execute('SELECT * FROM cash_advances WHERE id=?',(advance_id,)).fetchone()
    if not row: c.close(); raise HTTPException(404,'Avans kaydı bulunamadı.')
    prepared=[]; total=0.0
    for i,it in enumerate(items,1):
        st=(it.settlement_type or 'FIS').strip().upper()
        amt=float(it.amount or 0)
        doc=(it.document_no or '').strip()
        note=(it.note or '').strip()
        docdate=(it.document_date or '').strip() or datetime.now().strftime('%Y-%m-%d')
        if st not in ('FATURA','FIS','NAKIT_IADE','MAHSUP'):
            c.close(); raise HTTPException(400,f'{i}. satırda geçersiz belge türü.')
        if amt<=0:
            c.close(); raise HTTPException(400,f'{i}. satırda tutar zorunlu ve 0 dan büyük olmalı.')
        if st in ('FATURA','FIS') and not doc:
            c.close(); raise HTTPException(400,f'{i}. satırda fiş/fatura numarası zorunlu.')
        prepared.append((st,amt,doc,note,docdate))
        total+=amt
    remaining=max(0,float(row['amount'] or 0)-float(row['settled_amount'] or 0))
    if total>remaining+0.0001:
        c.close(); raise HTTPException(400,f'Belge toplamı kalan avansı aşamaz. Kalan: {remaining:g} / Girilen: {total:g}')
    user=CURRENT_AUTH_USER.get() or {}; username=user.get('username','') if isinstance(user,dict) else ''
    cols=[r['name'] for r in c.execute('PRAGMA table_info(cash_advance_settlements)')]
    if 'document_date' not in cols:
        c.execute("ALTER TABLE cash_advance_settlements ADD COLUMN document_date TEXT DEFAULT ''")
    try:
        for st,amt,doc,note,docdate in prepared:
            c.execute("""INSERT INTO cash_advance_settlements(advance_id,settlement_type,amount,document_no,note,document_date,created_at,created_by)
              VALUES(?,?,?,?,?,?,DATETIME('now','localtime'),?)""",(advance_id,st,amt,doc,note,docdate,username))
        newsettled=float(row['settled_amount'] or 0)+total
        status='KAPANDI' if newsettled>=float(row['amount'] or 0)-0.0001 else 'KISMI'
        c.execute("UPDATE cash_advances SET settled_amount=?,status=?,updated_at=DATETIME('now','localtime'),updated_by=? WHERE id=?",(newsettled,status,username,advance_id))
        c.commit()
    except Exception:
        c.rollback(); c.close(); raise
    c.close()
    return {'ok':True,'count':len(prepared),'total':total,'status':status,'settled_amount':newsettled,'remaining':max(0,float(row['amount'] or 0)-newsettled)}

"""+endpoint_anchor
if endpoint_anchor not in s:
    raise RuntimeError('settlement endpoint anchor not found')
s=s.replace(endpoint_anchor,endpoint_insert,1)

button_old="""<button class=\"btn green\" onclick=\"openAdvanceSettlement(${x.id})\">FATURA / FİŞ / İADE</button><button class=\"btn secondary\" onclick=\"openAdvanceHistory(${x.id})\">GEÇMİŞ</button>"""
button_new="""<button class=\"btn green\" onclick=\"openAdvanceSettlement(${x.id})\">TEK BELGE</button><button class=\"btn primary\" onclick=\"openAdvanceBulkDocuments(${x.id})\">TOPLU FİŞ / FATURA</button><button class=\"btn secondary\" onclick=\"openAdvanceHistory(${x.id})\">GEÇMİŞ</button>"""
if button_old not in s:
    raise RuntimeError('advance action buttons anchor not found')
s=s.replace(button_old,button_new,1)

js_anchor="""function openAdvanceSettlement(id){"""
js_block=r'''
// SAMA_ADVANCE_BULK_DOCUMENTS_V1
window._advBulkSeq=0;
function advBulkAddRow(pref={}){
 const body=document.getElementById('advBulkRows'); if(!body)return;
 const id=++window._advBulkSeq;
 body.insertAdjacentHTML('beforeend',`<tr data-bulk-row="${id}">
  <td><input class="abDate" type="date" value="${pref.document_date||''}" title="Boş bırakılırsa kayıt tarihi kullanılır"></td>
  <td><select class="abType"><option value="FIS">FİŞ</option><option value="FATURA">FATURA</option><option value="NAKIT_IADE">NAKİT İADE</option><option value="MAHSUP">MAHSUP</option></select></td>
  <td><input class="abDoc" value="${String(pref.document_no||'').replace(/"/g,'&quot;')}" placeholder="Fiş/Fatura No *"></td>
  <td><input class="abNote" value="${String(pref.note||'').replace(/"/g,'&quot;')}" placeholder="Açıklama (opsiyonel)"></td>
  <td><input class="abAmount" type="number" min="0" step="1" value="${pref.amount||''}" placeholder="Tutar *" oninput="advBulkCalc()"></td>
  <td><button type="button" class="btn secondary" onclick="this.closest('tr').remove();advBulkCalc()">Sil</button></td>
 </tr>`);
 const tr=body.lastElementChild; tr.querySelector('.abType').value=pref.settlement_type||'FIS';
 advBulkCalc();
}
function advBulkRowsData(){
 return [...document.querySelectorAll('#advBulkRows tr')].map(tr=>({
  document_date:tr.querySelector('.abDate')?.value||'', settlement_type:tr.querySelector('.abType')?.value||'FIS',
  document_no:tr.querySelector('.abDoc')?.value||'', note:tr.querySelector('.abNote')?.value||'',
  amount:Number(tr.querySelector('.abAmount')?.value||0)
 })).filter(x=>x.amount>0||x.document_no||x.note||x.document_date);
}
function advBulkCalc(){
 const x=window._advBulkCurrent||{}; const rows=advBulkRowsData();
 const total=rows.reduce((a,r)=>a+Number(r.amount||0),0); const current=Number(x.settled_amount||0); const amount=Number(x.amount||0);
 const after=current+total; const remaining=amount-after;
 const cnt=document.getElementById('abCount'),tot=document.getElementById('abTotal'),rem=document.getElementById('abRemaining'),warn=document.getElementById('abWarn');
 if(cnt)cnt.innerText=rows.length; if(tot)tot.innerText=money(total)+' '+(x.currency||''); if(rem)rem.innerText=money(Math.max(0,remaining))+' '+(x.currency||'');
 if(warn){warn.innerText=remaining<0?'⚠ Girilen belge toplamı kalan avansı '+money(Math.abs(remaining))+' '+(x.currency||'')+' aşıyor.':'';warn.style.display=remaining<0?'block':'none';}
}
function openAdvanceBulkDocuments(id){
 const x=advanceRows.find(r=>Number(r.id)===Number(id)); if(!x)return;
 window._advBulkCurrent=x; window._advBulkSeq=0;
 const remain=Number(x.remaining||0);
 openM('Toplu Fiş / Fatura - '+(x.recipient_name||''),`<div class="detail-grid">
  <div class="detail-box"><span>Verilen Avans</span><strong>${money(x.amount)} ${x.currency||''}</strong></div>
  <div class="detail-box"><span>Daha Önce Belgelenen / İade</span><strong>${money(x.settled_amount)} ${x.currency||''}</strong></div>
  <div class="detail-box"><span>Kalan Bakiye</span><strong>${money(remain)} ${x.currency||''}</strong></div>
  <div class="detail-box"><span>SCNA / Plaka</span><strong>${x.scna||'-'} / ${x.plate||'-'}</strong></div>
 </div>
 <div class="filterbar"><b>Seri Belge Girişi</b><span class="section-note">Fiş/Fatura No ve Tutar zorunlu. Açıklama isteğe bağlı. Tarih boşsa kayıt tarihi kullanılır.</span><button type="button" class="btn secondary" onclick="advBulkAddRow()">+ Satır Ekle</button><button type="button" class="btn secondary" onclick="for(let i=0;i<10;i++)advBulkAddRow()">+ 10 Satır</button></div>
 <div class="table" style="max-height:420px;overflow:auto"><table><thead><tr><th>Tarih (boşsa bugün)</th><th>Tür</th><th>Fiş/Fatura No *</th><th>Açıklama</th><th>Tutar *</th><th></th></tr></thead><tbody id="advBulkRows"></tbody></table></div>
 <div class="cards" style="margin-top:12px"><div class="card">Belge Sayısı<b id="abCount">0</b></div><div class="card">Bu Giriş Toplamı<b id="abTotal">0</b></div><div class="card">Kayıt Sonrası Kalan<b id="abRemaining">${money(remain)} ${x.currency||''}</b></div></div>
 <div id="abWarn" class="diff-box diff-red" style="display:none"></div>`,async()=>{
   try{
    const items=advBulkRowsData(); if(!items.length)throw new Error('En az bir belge satırı girin.');
    for(let i=0;i<items.length;i++){
      const r=items[i];
      if(Number(r.amount||0)<=0)throw new Error((i+1)+'. satırda tutar zorunlu.');
      if((r.settlement_type==='FIS'||r.settlement_type==='FATURA')&&!String(r.document_no||'').trim())throw new Error((i+1)+'. satırda fiş/fatura numarası zorunlu.');
    }
    const total=items.reduce((a,r)=>a+Number(r.amount||0),0); if(total>Number(x.remaining||0)+0.0001)throw new Error('Belge toplamı kalan avansı aşıyor.');
    const r=await api('/api/advances/'+id+'/settlements/bulk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items})});
    closeM(); await loadAdvances(); alert(r.count+' belge kaydedildi. Toplam: '+money(r.total)+' '+(x.currency||''));
   }catch(e){alert(e.message);}
 });
 for(let i=0;i<10;i++)advBulkAddRow();
}

'''
if js_anchor not in s:
    raise RuntimeError('JS settlement function anchor not found')
s=s.replace(js_anchor,js_block+js_anchor,1)

hist_old="""<td>${fmtDateTime(z.created_at)}</td><td>${z.settlement_type}</td><td>${money(z.amount)}</td><td>${z.document_no||''}</td><td>${z.note||''}</td><td>${z.created_by||''}</td>"""
hist_new="""<td>${z.document_date||fmtDateTime(z.created_at)}</td><td>${z.settlement_type}</td><td>${money(z.amount)}</td><td>${z.document_no||''}</td><td>${z.note||''}</td><td>${z.created_by||''}</td>"""
if hist_old in s:
    s=s.replace(hist_old,hist_new,1)

p.write_text(s,encoding='utf-8')
print('patched advance bulk documents')
