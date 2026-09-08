from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
marker='# SAMA_ADVANCE_SETTLEMENT_EDIT_V1'
if marker in s:
    print('already patched'); raise SystemExit(0)

old="""class AdvanceSettlementIn(BaseModel):
    settlement_type: str = 'FATURA'
    amount: float = 0
    document_no: str = ''
    note: str = ''
"""
new="""class AdvanceSettlementIn(BaseModel):
    settlement_type: str = 'FATURA'
    amount: float = 0
    document_no: str = ''
    note: str = ''

# SAMA_ADVANCE_SETTLEMENT_EDIT_V1
class AdvanceSettlementUpdateIn(BaseModel):
    settlement_type: str = 'FATURA'
    amount: float = 0
    document_no: str = ''
    note: str = ''
    settlement_date: str = ''
"""
if old not in s: raise SystemExit('AdvanceSettlementIn block not found')
s=s.replace(old,new,1)

old2="""def advances_settlement(advance_id:int,x:AdvanceSettlementIn):
    st=(x.settlement_type or 'FATURA').strip().upper(); amt=float(x.amount or 0)
    if st not in ('FATURA','FIS','NAKIT_IADE','MAHSUP'): raise HTTPException(400,'Geçersiz kapatma türü.')
    if amt<=0: raise HTTPException(400,'Tutar 0 dan büyük olmalı.')
"""
new2="""def advances_settlement(advance_id:int,x:AdvanceSettlementIn):
    st=(x.settlement_type or 'FATURA').strip().upper(); amt=float(x.amount or 0); doc=(x.document_no or '').strip()
    if st not in ('FATURA','FIS','NAKIT_IADE','MAHSUP'): raise HTTPException(400,'Geçersiz kapatma türü.')
    if amt<=0: raise HTTPException(400,'Tutar 0 dan büyük olmalı.')
    if st in ('FATURA','FIS') and not doc: raise HTTPException(400,'Fatura/Fiş belge numarası zorunlu.')
"""
if old2 not in s: raise SystemExit('advances_settlement header not found')
s=s.replace(old2,new2,1)
s=s.replace("(advance_id,st,amt,(x.document_no or '').strip(),(x.note or '').strip(),username))","(advance_id,st,amt,doc,(x.note or '').strip(),username))",1)

anchor="""@app.get('/api/advances/{advance_id}/settlements')
def advances_settlements(advance_id:int):
    c=db(); _ensure_advances(c)
    rows=[dict(r) for r in c.execute('SELECT * FROM cash_advance_settlements WHERE advance_id=? ORDER BY id DESC',(advance_id,))]
    c.close(); return rows
"""
insert="""@app.patch('/api/advances/{advance_id}/settlements/{settlement_id}')
def advances_settlement_update(advance_id:int,settlement_id:int,x:AdvanceSettlementUpdateIn,request:Request):
    _require_user_perm(request,'users.manage')
    st=(x.settlement_type or 'FATURA').strip().upper(); amt=float(x.amount or 0); doc=(x.document_no or '').strip()
    if st not in ('FATURA','FIS','NAKIT_IADE','MAHSUP'): raise HTTPException(400,'Geçersiz kapatma türü.')
    if amt<=0: raise HTTPException(400,'Tutar 0 dan büyük olmalı.')
    if st in ('FATURA','FIS') and not doc: raise HTTPException(400,'Fatura/Fiş belge numarası zorunlu.')
    day=(x.settlement_date or '').strip()
    if day:
        try: datetime.strptime(day[:10],'%Y-%m-%d')
        except Exception: raise HTTPException(400,'Geçersiz işlem tarihi.')
    c=db(); _ensure_advances(c)
    adv=c.execute('SELECT * FROM cash_advances WHERE id=?',(advance_id,)).fetchone()
    row=c.execute('SELECT * FROM cash_advance_settlements WHERE id=? AND advance_id=?',(settlement_id,advance_id)).fetchone()
    if not adv or not row:
        c.close(); raise HTTPException(404,'Avans hareketi bulunamadı.')
    other=float(c.execute('SELECT COALESCE(SUM(amount),0) s FROM cash_advance_settlements WHERE advance_id=? AND id<>?',(advance_id,settlement_id)).fetchone()['s'] or 0)
    newsettled=other+amt
    advance_amount=float(adv['amount'] or 0)
    if newsettled>advance_amount+0.0001:
        c.close(); raise HTTPException(400,f'Düzeltilen tutarla toplam belgelenen avansı aşamaz. Avans: {advance_amount:g} / Toplam: {newsettled:g}')
    user=_request_user(request) or {}; username=user.get('username','') if isinstance(user,dict) else ''
    old_value=f\"Tür={row['settlement_type']} | Tutar={float(row['amount'] or 0):g} | Belge={row['document_no'] or ''} | Tarih={row['created_at'] or ''} | Açıklama={row['note'] or ''}\"
    if day:
        c.execute(\"UPDATE cash_advance_settlements SET settlement_type=?,amount=?,document_no=?,note=?,created_at=?||' 12:00:00' WHERE id=? AND advance_id=?\",(st,amt,doc,(x.note or '').strip(),day[:10],settlement_id,advance_id))
    else:
        c.execute('UPDATE cash_advance_settlements SET settlement_type=?,amount=?,document_no=?,note=? WHERE id=? AND advance_id=?',(st,amt,doc,(x.note or '').strip(),settlement_id,advance_id))
    status='KAPANDI' if newsettled>=advance_amount-0.0001 else ('KISMI' if newsettled>0 else 'ACIK')
    c.execute(\"UPDATE cash_advances SET settled_amount=?,status=?,updated_at=DATETIME('now','localtime'),updated_by=? WHERE id=?\",(newsettled,status,username,advance_id))
    c.commit(); c.close()
    new_value=f\"Tür={st} | Tutar={amt:g} | Belge={doc} | Tarih={day or row['created_at'] or ''} | Açıklama={(x.note or '').strip()}\"
    audit('ADVANCE_SETTLEMENT_UPDATE',str(advance_id),f'Avans hareketi düzeltildi. Hareket ID: {settlement_id}','AVANS',old_value,new_value)
    return {'ok':True,'status':status,'settled_amount':newsettled,'remaining':max(0,advance_amount-newsettled)}

"""+anchor
if anchor not in s: raise SystemExit('settlements endpoint anchor not found')
s=s.replace(anchor,insert,1)

old3="""async function openAdvanceHistory(id){const rows=await api('/api/advances/'+id+'/settlements');const x=advanceRows.find(r=>Number(r.id)===Number(id));openM(`${x?.recipient_name||''} — Avans Geçmişi`,`<div class=\"table\"><table><thead><tr><th>TARİH</th><th>TÜR</th><th>TUTAR</th><th>BELGE NO</th><th>AÇIKLAMA</th><th>GİREN</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${fmtDateTime(r.created_at)}</td><td>${r.settlement_type}</td><td>${money(r.amount)} ${x?.currency||''}</td><td>${r.document_no||''}</td><td>${r.note||''}</td><td>${r.created_by||''}</td></tr>`).join('')}</tbody></table></div>`,()=>closeM());}
"""
new3="""function advEsc(v){return String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;').replace(/'/g,'&#39;');}
async function openAdvanceHistory(id){const rows=await api('/api/advances/'+id+'/settlements');const x=advanceRows.find(r=>Number(r.id)===Number(id));window._advanceHistoryRows=rows;openM(`${x?.recipient_name||''} — Avans Geçmişi`,`<div class=\"table\"><table><thead><tr><th>TARİH</th><th>TÜR</th><th>TUTAR</th><th>BELGE NO</th><th>AÇIKLAMA</th><th>GİREN</th><th>İŞLEM</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${fmtDateTime(r.created_at)}</td><td>${advEsc(r.settlement_type)}</td><td>${money(r.amount)} ${advEsc(x?.currency||'')}</td><td>${advEsc(r.document_no||'')}</td><td>${advEsc(r.note||'')}</td><td>${advEsc(r.created_by||'')}</td><td><button class=\"btn secondary\" onclick=\"editAdvanceSettlement(${id},${r.id})\">DÜZELT</button></td></tr>`).join('')}</tbody></table></div>`,()=>closeM());}
function editAdvanceSettlement(advanceId,settlementId){const r=(window._advanceHistoryRows||[]).find(z=>Number(z.id)===Number(settlementId));const x=advanceRows.find(z=>Number(z.id)===Number(advanceId));if(!r)return;const day=String(r.created_at||'').slice(0,10);openM(`${x?.recipient_name||''} — Hareketi Düzelt`,`<div class=\"calc\"><b>Bu işlem mevcut hareketi düzeltir; yeni hareket oluşturmaz.</b><br><span class=\"small\">Değişiklik işlem geçmişine kaydedilir.</span></div><div class=\"grid\" style=\"margin-top:12px\"><div class=\"field\"><label>İşlem Türü</label><select id=\"aseType\"><option value=\"FATURA\">Fatura</option><option value=\"FIS\">Fiş</option><option value=\"NAKIT_IADE\">Nakit İade</option><option value=\"MAHSUP\">Mahsup</option></select></div><div class=\"field\"><label>Tutar</label><input id=\"aseAmount\" type=\"number\" min=\"0\" step=\"1\" value=\"${Number(r.amount||0)}\"></div><div class=\"field\"><label>Belge No</label><input id=\"aseDoc\" value=\"${advEsc(r.document_no||'')}\"></div><div class=\"field\"><label>İşlem Tarihi</label><input id=\"aseDate\" type=\"date\" value=\"${advEsc(day)}\"></div><div class=\"field wide\"><label>Açıklama</label><textarea id=\"aseNote\">${advEsc(r.note||'')}</textarea></div></div>`,async()=>{try{await api('/api/advances/'+advanceId+'/settlements/'+settlementId,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({settlement_type:aseType.value,amount:Number(aseAmount.value||0),document_no:aseDoc.value,note:aseNote.value,settlement_date:aseDate.value})});closeM();await loadAdvances();await openAdvanceHistory(advanceId);alert('Avans hareketi düzeltildi.');}catch(e){alert(e.message);}});setTimeout(()=>{aseType.value=r.settlement_type||'FATURA';},0);}
"""
if old3 not in s: raise SystemExit('openAdvanceHistory block not found')
s=s.replace(old3,new3,1)
p.write_text(s,encoding='utf-8')
print('patched advance settlement edit v1')
