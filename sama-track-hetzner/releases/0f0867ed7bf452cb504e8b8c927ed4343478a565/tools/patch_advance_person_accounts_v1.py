from pathlib import Path
p=Path('app.py'); s=p.read_text(encoding='utf-8')
MARK='# SAMA_ADVANCE_PERSON_ACCOUNTS_V1'
if MARK in s: print('already patched'); raise SystemExit
# models + endpoints before advances list
anchor="@app.get('/api/advances')\ndef advances_list(status:str=''):"
if anchor not in s: raise SystemExit('advances list anchor not found')
block=r'''# SAMA_ADVANCE_PERSON_ACCOUNTS_V1
class AdvanceOffsetIn(BaseModel):
    new_need: float = 0
    purpose: str = ''
    plate: str = ''
    scna: str = ''
    note: str = ''
    currency: str = 'IQD'

@app.get('/api/advances/person-accounts')
def advances_person_accounts(q:str='', recipient_type:str=''):
    c=db(); _ensure_advances(c)
    par=[]; where=["TRIM(COALESCE(recipient_name,''))<>''"]
    if (q or '').strip(): where.append('UPPER(recipient_name) LIKE UPPER(?)'); par.append('%'+q.strip()+'%')
    if (recipient_type or '').strip(): where.append('recipient_type=?'); par.append(recipient_type.strip().upper())
    rows=[dict(r) for r in c.execute(f"""SELECT recipient_type,recipient_name,currency,
      COUNT(*) advance_count,ROUND(SUM(amount),2) total_advance,ROUND(SUM(settled_amount),2) total_settled,
      ROUND(SUM(MAX(amount-settled_amount,0)),2) open_balance,
      SUM(CASE WHEN status IN ('ACIK','KISMI') THEN 1 ELSE 0 END) open_count,MAX(id) last_id
      FROM cash_advances WHERE {' AND '.join(where)}
      GROUP BY recipient_type,UPPER(TRIM(recipient_name)),currency
      ORDER BY open_balance DESC,recipient_name LIMIT 1000""",par)]
    c.close(); return rows

@app.get('/api/advances/person-account')
def advances_person_account(recipient_type:str,recipient_name:str,currency:str='IQD'):
    typ=(recipient_type or '').strip().upper(); name=(recipient_name or '').strip(); cur=(currency or 'IQD').strip().upper()
    c=db(); _ensure_advances(c)
    advances=[dict(r) for r in c.execute("""SELECT a.*,MAX(0,a.amount-a.settled_amount) remaining FROM cash_advances a
      WHERE recipient_type=? AND UPPER(TRIM(recipient_name))=UPPER(TRIM(?)) AND currency=? ORDER BY id DESC""",(typ,name,cur))]
    movements=[]
    for a in advances:
        movements.append({'date':a.get('created_at'),'kind':'AVANS','amount':float(a.get('amount') or 0),'advance_id':a['id'],'document_no':'','note':a.get('purpose') or ''})
        for r in c.execute("SELECT * FROM cash_advance_settlements WHERE advance_id=? ORDER BY id",(a['id'],)):
            d=dict(r); movements.append({'date':d.get('created_at'),'kind':d.get('settlement_type'),'amount':-float(d.get('amount') or 0),'advance_id':a['id'],'document_no':d.get('document_no') or '','note':d.get('note') or ''})
    movements.sort(key=lambda z:str(z.get('date') or ''),reverse=True)
    total=sum(float(a.get('amount') or 0) for a in advances); settled=sum(float(a.get('settled_amount') or 0) for a in advances)
    c.close(); return {'recipient_type':typ,'recipient_name':name,'currency':cur,'total_advance':total,'total_settled':settled,'open_balance':max(0,total-settled),'advances':advances,'movements':movements}

@app.post('/api/advances/person-account/offset')
def advances_person_account_offset(recipient_type:str,recipient_name:str,x:AdvanceOffsetIn,request:Request):
    _require_user_perm(request,'users.manage')
    typ=(recipient_type or '').strip().upper(); name=(recipient_name or '').strip(); cur=(x.currency or 'IQD').strip().upper(); need=float(x.new_need or 0)
    if typ not in ('SOFOR','USTA','PERSONEL','DIGER') or not name: raise HTTPException(400,'Kişi bilgisi geçersiz.')
    if need<=0: raise HTTPException(400,'Yeni avans ihtiyacı 0 dan büyük olmalı.')
    if not (x.purpose or '').strip(): raise HTTPException(400,'Yeni avans nedeni zorunlu.')
    c=db(); _ensure_advances(c)
    olds=[dict(r) for r in c.execute("""SELECT * FROM cash_advances WHERE recipient_type=? AND UPPER(TRIM(recipient_name))=UPPER(TRIM(?)) AND currency=? AND status IN ('ACIK','KISMI') AND amount>settled_amount ORDER BY id""",(typ,name,cur))]
    available=sum(max(0,float(a['amount'] or 0)-float(a['settled_amount'] or 0)) for a in olds)
    offset=min(need,available); left=offset
    user=_request_user(request) or {}; username=user.get('username','') if isinstance(user,dict) else ''
    for a in olds:
        if left<=0: break
        rem=max(0,float(a['amount'] or 0)-float(a['settled_amount'] or 0)); use=min(rem,left)
        if use<=0: continue
        c.execute("INSERT INTO cash_advance_settlements(advance_id,settlement_type,amount,document_no,note,created_at,created_by) VALUES(?, 'MAHSUP', ?, '', ?, DATETIME('now','localtime'),?)",(a['id'],use,'Yeni avans ihtiyacına mahsup: '+(x.purpose or '').strip(),username))
        ns=float(a['settled_amount'] or 0)+use; status='KAPANDI' if ns>=float(a['amount'] or 0)-0.0001 else 'KISMI'
        c.execute("UPDATE cash_advances SET settled_amount=?,status=?,updated_at=DATETIME('now','localtime'),updated_by=? WHERE id=?",(ns,status,username,a['id']))
        left-=use
    cash_to_give=max(0,need-offset); new_id=None
    if cash_to_give>0:
        c.execute("""INSERT INTO cash_advances(recipient_type,recipient_name,plate,scna,purpose,amount,currency,note,status,created_at,created_by)
          VALUES(?,?,?,?,?,?,?,?,'ACIK',DATETIME('now','localtime'),?)""",(typ,name,(x.plate or '').strip().upper(),(x.scna or '').strip().upper(),(x.purpose or '').strip(),cash_to_give,cur,(x.note or '').strip(),username))
        new_id=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    c.commit(); c.close()
    audit('ADVANCE_PERSON_OFFSET',name,f'Yeni ihtiyaç {need:g} {cur}; mahsup {offset:g}; kasadan verilen {cash_to_give:g}','AVANS')
    return {'ok':True,'new_need':need,'offset':offset,'cash_to_give':cash_to_give,'new_advance_id':new_id}

'''
s=s.replace(anchor,block+anchor,1)
# add UI button to advance page header by injecting JS helper before openAdvanceNew
jsanchor='function openAdvanceNew(){'
if jsanchor not in s: raise SystemExit('openAdvanceNew anchor not found')
js=r'''// SAMA_ADVANCE_PERSON_ACCOUNTS_UI_V1
async function openAdvancePersonAccounts(){
 try{const rows=await api('/api/advances/person-accounts');const body=rows.length?rows.map((x,i)=>`<tr><td>${advEsc(x.recipient_type)}</td><td><b>${advEsc(x.recipient_name)}</b></td><td>${advEsc(x.currency)}</td><td>${money(x.total_advance)}</td><td>${money(x.total_settled)}</td><td><b>${money(x.open_balance)}</b></td><td>${x.open_count||0}</td><td><button class="btn secondary" onclick="openAdvancePersonDetail(${i})">HESAP</button></td></tr>`).join(''):'<tr><td colspan="8">Kişi hesabı bulunamadı.</td></tr>';window._advancePersonRows=rows;openM('KİŞİ / CARİ HESAPLARI',`<div class="section-note">Avans, fatura/fiş, iade ve mahsuplar kişi bazında tek hesapta gösterilir.</div><div class="table"><table><thead><tr><th>TİP</th><th>KİŞİ</th><th>PB</th><th>VERİLEN AVANS</th><th>KAPANAN</th><th>AÇIK BAKİYE</th><th>AÇIK KAYIT</th><th>İŞLEM</th></tr></thead><tbody>${body}</tbody></table></div>`,()=>closeM());}catch(e){alert(e.message)}
}
async function openAdvancePersonDetail(i){const p=(window._advancePersonRows||[])[i];if(!p)return;try{const x=await api('/api/advances/person-account?recipient_type='+encodeURIComponent(p.recipient_type)+'&recipient_name='+encodeURIComponent(p.recipient_name)+'&currency='+encodeURIComponent(p.currency));window._advancePersonCurrent=x;const body=(x.movements||[]).map(m=>`<tr><td>${fmtDateTime(m.date)}</td><td>${advEsc(m.kind)}</td><td>${m.amount>=0?money(m.amount):''}</td><td>${m.amount<0?money(-m.amount):''}</td><td>${advEsc(m.document_no||'')}</td><td>${advEsc(m.note||'')}</td></tr>`).join('');openM(`${advEsc(x.recipient_name)} — Kişi Hesabı`,`<div class="calc"><b>Toplam Avans:</b> ${money(x.total_advance)} ${x.currency} &nbsp; <b>Kapanan:</b> ${money(x.total_settled)} &nbsp; <b>Açık Bakiye:</b> ${money(x.open_balance)}</div><div style="margin:10px 0"><button class="btn green" onclick="openAdvancePersonOffset()">YENİ AVANS / MAHSUP</button></div><div class="table"><table><thead><tr><th>TARİH</th><th>İŞLEM</th><th>AVANS</th><th>FATURA/İADE/MAHSUP</th><th>BELGE</th><th>AÇIKLAMA</th></tr></thead><tbody>${body}</tbody></table></div>`,()=>closeM());}catch(e){alert(e.message)}}
function openAdvancePersonOffset(){const x=window._advancePersonCurrent;if(!x)return;openM(`${advEsc(x.recipient_name)} — Yeni Avans / Mahsup`,`<div class="calc"><b>Mevcut açık bakiye:</b> ${money(x.open_balance)} ${x.currency}<br><span class="small">Yeni ihtiyaçtan mevcut bakiye otomatik mahsup edilir. Sadece gerçekten verilen nakit yeni avans/kasa çıkışı olur.</span></div><div class="grid" style="margin-top:12px"><div class="field"><label>Yeni Avans İhtiyacı</label><input id="apoNeed" type="number" min="0" step="1" oninput="calcAdvanceOffset()"></div><div class="field"><label>Eski Bakiyeden Mahsup</label><input id="apoOffset" disabled></div><div class="field"><label>Kasadan Verilecek</label><input id="apoCash" disabled></div><div class="field wide"><label>Yeni İş / Avans Nedeni</label><input id="apoPurpose"></div><div class="field"><label>Plaka</label><input id="apoPlate"></div><div class="field"><label>SCNA</label><input id="apoScna"></div><div class="field wide"><label>Not</label><input id="apoNote"></div></div>`,async()=>{try{const need=Number(apoNeed.value||0),off=Math.min(need,Number(x.open_balance||0)),cash=Math.max(0,need-off);if(!confirm(`Yeni ihtiyaç: ${money(need)} ${x.currency}\nMahsup: ${money(off)}\nKasadan verilecek: ${money(cash)}\n\nİşlem kaydedilsin mi?`))return;await api('/api/advances/person-account/offset?recipient_type='+encodeURIComponent(x.recipient_type)+'&recipient_name='+encodeURIComponent(x.recipient_name),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_need:need,purpose:apoPurpose.value,plate:apoPlate.value,scna:apoScna.value,note:apoNote.value,currency:x.currency})});closeM();await loadAdvances();alert('Mahsup ve yeni avans işlemi kaydedildi.');}catch(e){alert(e.message)}});calcAdvanceOffset();}
function calcAdvanceOffset(){const x=window._advancePersonCurrent||{},need=Number(document.getElementById('apoNeed')?.value||0),off=Math.min(need,Number(x.open_balance||0)),cash=Math.max(0,need-off);if(document.getElementById('apoOffset'))apoOffset.value=off;if(document.getElementById('apoCash'))apoCash.value=cash;}

'''
s=s.replace(jsanchor,js+jsanchor,1)
# add button near Yeni Avans if exact common text exists
needle='<button class="btn green" onclick="openAdvanceNew()">+ Yeni Avans</button>'
if needle in s: s=s.replace(needle,needle+'<button class="btn secondary" onclick="openAdvancePersonAccounts()">KİŞİ / CARİ HESAPLARI</button>',1)
else:
    # fallback insert into advances page heading near onclick
    idx=s.find('onclick="openAdvanceNew()"')
    if idx<0: raise SystemExit('new advance button not found')
    end=s.find('</button>',idx)+9
    s=s[:end]+'<button class="btn secondary" onclick="openAdvancePersonAccounts()">KİŞİ / CARİ HESAPLARI</button>'+s[end:]
p.write_text(s,encoding='utf-8'); print('patched')
