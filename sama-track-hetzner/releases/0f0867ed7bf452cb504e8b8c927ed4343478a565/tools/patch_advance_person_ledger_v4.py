from pathlib import Path
p=Path('app.py'); s=p.read_text(encoding='utf-8')
MARK='# SAMA_ADVANCE_PERSON_LEDGER_V4'
if MARK in s:
    print('already patched'); raise SystemExit
anchor='# SAMA_ADVANCE_PERSON_ACCOUNTS_V1\n'
if anchor not in s: raise SystemExit('person account anchor missing')
s=s.replace(anchor, anchor+MARK+'\n',1)

# Add person-level settlement model and reconciliation helpers before AdvanceOffsetIn
needle="class AdvanceOffsetIn(BaseModel):\n"
insert=r'''class AdvancePersonSettlementIn(BaseModel):
    settlement_type: str = 'FATURA'
    amount: float = 0
    document_no: str = ''
    note: str = ''
    currency: str = 'IQD'


def _advance_person_metrics(c, typ:str, name:str, cur:str):
    typ=(typ or '').strip().upper(); name=(name or '').strip(); cur=(cur or 'IQD').strip().upper()
    row=c.execute("""SELECT COALESCE(SUM(amount),0) total_advance,
        COALESCE(SUM(settled_amount),0) total_settled,COUNT(*) record_count
      FROM cash_advances
      WHERE recipient_type=? AND UPPER(TRIM(recipient_name))=UPPER(TRIM(?)) AND currency=?""",(typ,name,cur)).fetchone()
    total=float(row['total_advance'] or 0); settled=float(row['total_settled'] or 0); bal=total-settled
    state='KAPANDI' if abs(bal)<0.0001 else ('BORCLU' if bal>0 else 'ALACAKLI')
    return {'total_advance':total,'total_settled':settled,'balance':bal,'account_status':state,'record_count':int(row['record_count'] or 0)}


def _reconcile_advance_person(c, typ:str, name:str, cur:str, username:str=''):
    """Settlement rows are the source of truth; cached settled/status fields are rebuilt safely."""
    rows=[dict(r) for r in c.execute("""SELECT id,amount FROM cash_advances
      WHERE recipient_type=? AND UPPER(TRIM(recipient_name))=UPPER(TRIM(?)) AND currency=? ORDER BY id""",
      ((typ or '').strip().upper(),(name or '').strip(),(cur or 'IQD').strip().upper()))]
    for a in rows:
        settled=float(c.execute('SELECT COALESCE(SUM(amount),0) FROM cash_advance_settlements WHERE advance_id=?',(a['id'],)).fetchone()[0] or 0)
        amount=float(a['amount'] or 0)
        st='KAPANDI' if settled>=amount-0.0001 else ('KISMI' if settled>0 else 'ACIK')
        c.execute("UPDATE cash_advances SET settled_amount=?,status=?,updated_at=COALESCE(updated_at,DATETIME('now','localtime')),updated_by=CASE WHEN ?<>'' THEN ? ELSE updated_by END WHERE id=?",
                  (settled,st,username,username,a['id']))
    return _advance_person_metrics(c,typ,name,cur)

'''
if needle not in s: raise SystemExit('AdvanceOffsetIn anchor missing')
s=s.replace(needle,insert+needle,1)

# Replace person-accounts aggregation with account-level status driven by signed balance.
old="""rows=[dict(r) for r in c.execute(f\"\"\"SELECT recipient_type,recipient_name,currency,\n      COUNT(*) advance_count,ROUND(SUM(amount),2) total_advance,ROUND(SUM(settled_amount),2) total_settled,\n      ROUND(SUM(amount-settled_amount),2) open_balance,\n      SUM(CASE WHEN status IN ('ACIK','KISMI') THEN 1 ELSE 0 END) open_count,MAX(id) last_id\n      FROM cash_advances WHERE {' AND '.join(where)}\n      GROUP BY recipient_type,UPPER(TRIM(recipient_name)),currency\n      ORDER BY open_balance DESC,recipient_name LIMIT 1000\"\"\",par)]\n    c.close(); return rows"""
new="""rows=[dict(r) for r in c.execute(f\"\"\"SELECT recipient_type,recipient_name,currency,\n      COUNT(*) advance_count,ROUND(SUM(amount),2) total_advance,ROUND(SUM(settled_amount),2) total_settled,\n      ROUND(SUM(amount-settled_amount),2) open_balance,MAX(id) last_id\n      FROM cash_advances WHERE {' AND '.join(where)}\n      GROUP BY recipient_type,UPPER(TRIM(recipient_name)),currency\n      ORDER BY ABS(SUM(amount-settled_amount)) DESC,recipient_name LIMIT 1000\"\"\",par)]\n    for r in rows:\n        b=float(r.get('open_balance') or 0); r['account_status']='KAPANDI' if abs(b)<0.0001 else ('BORCLU' if b>0 else 'ALACAKLI'); r['open_count']=1 if abs(b)>=0.0001 else 0\n    c.close(); return rows"""
if old not in s: raise SystemExit('person account aggregate anchor missing')
s=s.replace(old,new,1)

# Person detail: reconcile cache first and return authoritative account_status.
old="""    c=db(); _ensure_advances(c)\n    advances=[dict(r) for r in c.execute(\"\"\"SELECT a.*,(a.amount-a.settled_amount) remaining FROM cash_advances a"""
new="""    c=db(); _ensure_advances(c)\n    _reconcile_advance_person(c,typ,name,cur); c.commit()\n    advances=[dict(r) for r in c.execute(\"\"\"SELECT a.*,(a.amount-a.settled_amount) remaining FROM cash_advances a"""
if old not in s: raise SystemExit('person detail reconcile anchor missing')
s=s.replace(old,new,1)
oldret="c.close(); return {'recipient_type':typ,'recipient_name':name,'currency':cur,'total_advance':total,'total_settled':settled,'open_balance':total-settled,'advances':advances,'movements':movements}"
newret="metrics=_advance_person_metrics(c,typ,name,cur); c.close(); return {'recipient_type':typ,'recipient_name':name,'currency':cur,'total_advance':total,'total_settled':settled,'open_balance':total-settled,'account_status':metrics['account_status'],'advances':advances,'movements':movements}"
if oldret not in s: raise SystemExit('person detail return anchor missing')
s=s.replace(oldret,newret,1)

# Add person-level FIFO document endpoint before offset route.
offset_route="@app.post('/api/advances/person-account/offset')\n"
endpoint=r'''@app.post('/api/advances/person-account/settlement')
def advances_person_account_settlement(recipient_type:str,recipient_name:str,x:AdvancePersonSettlementIn,request:Request):
    _require_user_perm(request,'users.manage')
    typ=(recipient_type or '').strip().upper(); name=(recipient_name or '').strip(); cur=(x.currency or 'IQD').strip().upper()
    st=(x.settlement_type or 'FATURA').strip().upper(); amt=float(x.amount or 0); doc=(x.document_no or '').strip()
    if typ not in ('SOFOR','USTA','PERSONEL','DIGER') or not name: raise HTTPException(400,'Kişi bilgisi geçersiz.')
    if st not in ('FATURA','FIS'): raise HTTPException(400,'Cari belge türü FATURA veya FİŞ olmalı.')
    if amt<=0: raise HTTPException(400,'Tutar 0 dan büyük olmalı.')
    if not doc: raise HTTPException(400,'Fatura/Fiş belge numarası zorunlu.')
    c=db(); _ensure_advances(c)
    user=_request_user(request) or {}; username=user.get('username','') if isinstance(user,dict) else ''
    # Rebuild cached totals before allocation. Existing settlement rows remain the accounting source of truth.
    _reconcile_advance_person(c,typ,name,cur,username)
    advances=[dict(r) for r in c.execute("""SELECT * FROM cash_advances WHERE recipient_type=?
      AND UPPER(TRIM(recipient_name))=UPPER(TRIM(?)) AND currency=? ORDER BY id""",(typ,name,cur))]
    left=amt; allocated=[]
    for a in advances:
        if left<=0.0001: break
        rem=max(0,float(a['amount'] or 0)-float(a['settled_amount'] or 0))
        if rem<=0: continue
        use=min(rem,left)
        c.execute("""INSERT INTO cash_advance_settlements(advance_id,settlement_type,amount,document_no,note,created_at,created_by)
          VALUES(?,?,?,?,?,DATETIME('now','localtime'),?)""",(a['id'],st,use,doc,(x.note or '').strip(),username))
        allocated.append({'advance_id':a['id'],'amount':use}); left-=use
    # Excess document value is legitimate company debt to the person. Keep it on a carrier advance
    # so signed person balance remains exact; no fake cash movement is created.
    if left>0.0001:
        if advances:
            carrier=advances[-1]['id']
        else:
            c.execute("""INSERT INTO cash_advances(recipient_type,recipient_name,purpose,amount,currency,note,status,created_at,created_by)
              VALUES(?,?,?,0,?,?,'KAPANDI',DATETIME('now','localtime'),?)""",(typ,name,'CARİ BELGE DEVİR',cur,'Avanssız cari belge taşıyıcı kaydı',username))
            carrier=c.execute('SELECT last_insert_rowid()').fetchone()[0]
        c.execute("""INSERT INTO cash_advance_settlements(advance_id,settlement_type,amount,document_no,note,created_at,created_by)
          VALUES(?,?,?,?,?,DATETIME('now','localtime'),?)""",(carrier,st,left,doc,(x.note or '').strip(),username))
        allocated.append({'advance_id':carrier,'amount':left,'excess':True}); left=0
    metrics=_reconcile_advance_person(c,typ,name,cur,username)
    c.commit(); c.close()
    audit('ADVANCE_PERSON_SETTLEMENT',name,f'{st} {amt:g} {cur} belge {doc}; cari {metrics["balance"]:g}','AVANS')
    return {'ok':True,'allocated':allocated,'total_advance':metrics['total_advance'],'total_settled':metrics['total_settled'],'balance':metrics['balance'],'account_status':metrics['account_status']}

@app.post('/api/advances/person-account/reconcile')
def advances_person_account_reconcile(recipient_type:str,recipient_name:str,currency:str='IQD',request:Request=None):
    _require_user_perm(request,'users.manage')
    typ=(recipient_type or '').strip().upper(); name=(recipient_name or '').strip(); cur=(currency or 'IQD').strip().upper()
    if not name: raise HTTPException(400,'Kişi adı zorunlu.')
    c=db(); _ensure_advances(c)
    user=_request_user(request) or {}; username=user.get('username','') if isinstance(user,dict) else ''
    m=_reconcile_advance_person(c,typ,name,cur,username); c.commit(); c.close()
    audit('ADVANCE_PERSON_RECONCILE',name,f'Cari mutabakat yapıldı. Bakiye {m["balance"]:g} {cur}','AVANS')
    return {'ok':True,**m}

'''
if offset_route not in s: raise SystemExit('offset route anchor missing')
s=s.replace(offset_route,endpoint+offset_route,1)

# Make advances list carry person-level authoritative status.
old="""    rows=[dict(r) for r in c.execute(sql,par)]\n    c.close(); return rows"""
new="""    rows=[dict(r) for r in c.execute(sql,par)]\n    groups={}\n    for r in c.execute(\"\"\"SELECT recipient_type,UPPER(TRIM(recipient_name)) nm,currency,SUM(amount-settled_amount) balance\n      FROM cash_advances GROUP BY recipient_type,UPPER(TRIM(recipient_name)),currency\"\"\"):\n        b=float(r['balance'] or 0); groups[(r['recipient_type'],r['nm'],r['currency'])]=(b,'KAPANDI' if abs(b)<0.0001 else ('BORCLU' if b>0 else 'ALACAKLI'))\n    for x in rows:\n        b,st2=groups.get((x.get('recipient_type'),(x.get('recipient_name') or '').strip().upper(),x.get('currency')),(float(x.get('remaining') or 0),'ACIK'))\n        x['record_status']=x.get('status'); x['person_balance']=b; x['account_status']=st2\n    c.close(); return rows"""
if old not in s: raise SystemExit('advances list return anchor missing')
s=s.replace(old,new,1)

# recipient autocomplete should use signed account balance, not per-row status.
old="""             SUM(CASE WHEN status IN ('ACIK','KISMI') THEN 1 ELSE 0 END) open_count,\n             ROUND(SUM(CASE WHEN status IN ('ACIK','KISMI') THEN MAX(amount-settled_amount,0) ELSE 0 END),2) open_balance,"""
new="""             CASE WHEN ABS(SUM(amount-settled_amount))>=0.0001 THEN 1 ELSE 0 END open_count,\n             ROUND(SUM(amount-settled_amount),2) open_balance,"""
if old in s: s=s.replace(old,new,1)

# UI: filter/status becomes person account status.
s=s.replace("<option value=\"ACIK\">Açık</option><option value=\"KISMI\">Kısmi</option><option value=\"KAPANDI\">Kapandı</option>","<option value=\"BORCLU\">Borçlu</option><option value=\"ALACAKLI\">Alacaklı</option><option value=\"KAPANDI\">Kapalı</option>",1)
s=s.replace("(!st||x.status===st)","(!st||x.account_status===st)",1)
s=s.replace("<td>${x.status||''}</td><td><div class=\"compact-actions\">", "<td><b>${x.account_status||x.status||''}</b><div class=\"small\">Kayıt: ${x.record_status||x.status||''}</div></td><td><div class=\"compact-actions\">",1)
s=s.replace("const open=rows.filter(x=>x.status!=='KAPANDI');", "const open=rows.filter(x=>x.account_status!=='KAPANDI');",1)

# Person detail buttons/status and direct person document entry + reconciliation.
oldbtn="<div style=\"margin:10px 0\"><button class=\"btn green\" onclick=\"openAdvancePersonOffset()\">YENİ AVANS / MAHSUP</button></div>"
newbtn="<div style=\"margin:10px 0;display:flex;gap:8px;flex-wrap:wrap\"><button class=\"btn green\" onclick=\"openAdvancePersonOffset()\">YENİ AVANS / MAHSUP</button><button class=\"btn primary\" onclick=\"openAdvancePersonDocument()\">CARİYE FATURA / FİŞ</button><button class=\"btn secondary\" onclick=\"reconcileAdvancePerson()\">HESABI MUTABAKAT ET</button></div>"
if oldbtn not in s: raise SystemExit('person detail button anchor missing')
s=s.replace(oldbtn,newbtn,1)
s=s.replace("<b>Cari Bakiye:</b> ${money(x.open_balance)} <span class=\"small\">(+ kişi şirkete borçlu / - şirket kişiye borçlu)</span>","<b>Cari Bakiye:</b> ${money(x.open_balance)} ${x.currency} &nbsp; <b>Durum:</b> ${x.account_status||''}<br><span class=\"small\">Pozitif: kişi şirkete borçlu. Negatif: şirket kişiye borçlu.</span>",1)

insert_js=r'''
async function reconcileAdvancePerson(){
 const x=window._advancePersonCurrent;if(!x)return;
 try{const r=await api('/api/advances/person-account/reconcile?recipient_type='+encodeURIComponent(x.recipient_type)+'&recipient_name='+encodeURIComponent(x.recipient_name)+'&currency='+encodeURIComponent(x.currency),{method:'POST'});alert('Mutabakat tamamlandı. Cari bakiye: '+money(r.balance)+' '+x.currency+' / '+r.account_status);closeM();await openAdvancePersonAccounts();await loadAdvances();}catch(e){alert(e.message)}
}
function openAdvancePersonDocument(){
 const x=window._advancePersonCurrent;if(!x)return;
 openM(`${advEsc(x.recipient_name)} — Cariye Fatura / Fiş`,`<div class="section-note">Belge kişi hesabına girilir. Sistem eski açık avanslara FIFO dağıtır; fazlası kişi alacağı olarak eksi cari bakiyede kalır.</div><div class="grid"><div class="field"><label>Belge Türü</label><select id="apdType"><option value="FATURA">FATURA</option><option value="FIS">FİŞ</option></select></div><div class="field"><label>Belge No *</label><input id="apdDoc"></div><div class="field"><label>Tutar *</label><input id="apdAmount" type="number" min="0" step="1"></div><div class="field"><label>Para Birimi</label><input value="${x.currency}" disabled></div><div class="field wide"><label>Açıklama</label><input id="apdNote"></div></div>`,async()=>{try{const amt=Number(apdAmount.value||0),doc=apdDoc.value.trim();if(amt<=0)throw new Error('Tutar 0 dan büyük olmalı.');if(!doc)throw new Error('Belge numarası zorunlu.');const r=await api('/api/advances/person-account/settlement?recipient_type='+encodeURIComponent(x.recipient_type)+'&recipient_name='+encodeURIComponent(x.recipient_name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({settlement_type:apdType.value,amount:amt,document_no:doc,note:apdNote.value,currency:x.currency})});alert('Belge işlendi. Cari bakiye: '+money(r.balance)+' '+x.currency+' / '+r.account_status);closeM();await loadAdvances();await openAdvancePersonAccounts();}catch(e){alert(e.message)}});
}
'''
js_anchor="function openAdvancePersonOffset(){"
if js_anchor not in s: raise SystemExit('person JS anchor missing')
s=s.replace(js_anchor,insert_js+js_anchor,1)

p.write_text(s,encoding='utf-8'); print('patched person ledger v4')
