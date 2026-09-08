from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_CASH_EXPENSE_EDIT_PERMISSION_V1'
if MARK in s:
    print('already patched'); raise SystemExit(0)

# Permission catalog: ADMIN gets it automatically because ADMIN=set(PERMISSION_LABELS).
anchor='  "audit.view":"İşlem Geçmişi Gör",\n  "users.manage":"Kullanıcılar & Yetkiler Yönet",\n'
repl='  "audit.view":"İşlem Geçmişi Gör",\n  "cash.expense.edit":"Günlük Kasa Harcama Düzelt",\n  "users.manage":"Kullanıcılar & Yetkiler Yönet",\n'
if anchor not in s: raise RuntimeError('permission anchor not found')
s=s.replace(anchor,repl,1)

# Middleware routing for the protected PATCH endpoint.
anchor='    if path.startswith("/api/audit"):\n        return "audit.view"\n\n'
repl='    if path.startswith("/api/audit"):\n        return "audit.view"\n\n    if path.startswith("/api/cash-control/expense/") and m=="PATCH":\n        return "cash.expense.edit"\n\n'
if anchor not in s: raise RuntimeError('permission routing anchor not found')
s=s.replace(anchor,repl,1)

# Model near other input models.
anchor='class StatusIn(BaseModel):\n    status: str\n\n'
repl='class StatusIn(BaseModel):\n    status: str\n\nclass CashExpenseEditIn(BaseModel):\n    document_no: str = ""\n    amount: float = 0\n    note: str = ""\n    expense_date: str = ""\n    currency: str = "IQD"\n\n'
if anchor not in s: raise RuntimeError('model anchor not found')
s=s.replace(anchor,repl,1)

# Add endpoint before the JS block so route is registered server-side.
# Use a stable Python endpoint anchor known to be late in the file.
anchor='@app.get("/api/health")\ndef health():\n'
endpoint='''# SAMA_CASH_EXPENSE_EDIT_PERMISSION_V1
@app.patch("/api/cash-control/expense/{expense_id}")
def edit_cash_control_expense(expense_id:int, x:CashExpenseEditIn, request:Request):
    # Middleware already enforces cash.expense.edit. Keep a second explicit guard for clarity/safety.
    user=_request_user(request)
    if not user:
        raise HTTPException(401,"Oturum gerekli.")
    if user.get("role")!="ADMIN" and "cash.expense.edit" not in set(user.get("permissions") or []):
        raise HTTPException(403,"Günlük Kasa harcaması düzeltme yetkiniz yok.")

    doc=str(x.document_no or "").strip()
    note=str(x.note or "").strip()
    cur=str(x.currency or "IQD").strip().upper()
    day=str(x.expense_date or "").strip() or datetime.now().strftime("%Y-%m-%d")
    amount=float(x.amount or 0)
    if not doc:
        raise HTTPException(400,"Fatura/Fiş No gerekli.")
    if amount<=0:
        raise HTTPException(400,"Tutar 0’dan büyük olmalı.")
    if cur not in ("IQD","USD","TRY"):
        raise HTTPException(400,"Geçersiz para birimi.")
    try:
        datetime.strptime(day[:10],"%Y-%m-%d")
        day=day[:10]
    except Exception:
        raise HTTPException(400,"Tarih YYYY-MM-DD formatında olmalı.")

    c=db()
    old=c.execute("SELECT * FROM cash_daily_expenses WHERE id=?",(expense_id,)).fetchone()
    if not old:
        c.close(); raise HTTPException(404,"Harcama kaydı bulunamadı.")
    oldd=dict(old)
    c.execute("""UPDATE cash_daily_expenses
                 SET document_no=?,amount=?,note=?,expense_date=?,currency=?
                 WHERE id=?""",(doc,amount,note,day,cur,expense_id))
    c.commit(); c.close()
    audit("CASH_EXPENSE_EDIT",str(expense_id),
          f"Günlük kasa harcaması düzeltildi: {doc} / {amount:.2f} {cur}",
          "GUNLUK_KASA",
          f"{oldd.get('document_no','')} | {float(oldd.get('amount') or 0):.2f} {oldd.get('currency','')} | {oldd.get('expense_date','')} | {oldd.get('note','')}",
          f"{doc} | {amount:.2f} {cur} | {day} | {note}")
    return {"ok":True,"id":expense_id}

'''
if anchor not in s: raise RuntimeError('health anchor not found')
s=s.replace(anchor,endpoint+anchor,1)

# Add edit action to daily cash expense rows. Only authorized users see it.
old=" cashExpenseHistory.innerHTML=(cashSummary.expenses||[]).map(x=>`<tr><td>${x.expense_date||''}</td><td>${x.document_no||''}</td><td>${money(x.amount)} ${x.currency||''}</td><td>${x.note||''}</td><td>${x.created_by||''}</td></tr>`).join('');"
new=""" const canEditCashExpense=!!AUTH_USER && (AUTH_USER.role==='ADMIN' || (AUTH_USER.permissions||[]).includes('cash.expense.edit'));
 cashExpenseHistory.innerHTML=(cashSummary.expenses||[]).map(x=>`<tr><td>${x.expense_date||''}</td><td>${x.document_no||''}</td><td>${money(x.amount)} ${x.currency||''}</td><td>${x.note||''}</td><td>${x.created_by||''}</td><td>${canEditCashExpense?`<button class=\"btn\" onclick='openCashExpenseEdit(${JSON.stringify(x)})'>Düzelt</button>`:''}</td></tr>`).join('');"""
if old not in s: raise RuntimeError('cash history JS anchor not found')
s=s.replace(old,new,1)

# Add edit modal helper before openEntryCashMissing.
anchor='async function openEntryCashMissing(){\n'
js='''function openCashExpenseEdit(x){
 const can=!!AUTH_USER && (AUTH_USER.role==='ADMIN' || (AUTH_USER.permissions||[]).includes('cash.expense.edit'));
 if(!can)return alert('Bu işlem için yetkiniz yok.');
 openM('Günlük Kasa Harcaması Düzelt',`<div class="grid">
   <label>Fatura/Fiş No*<input id="ceDoc" value="${String(x.document_no||'').replace(/&/g,'&amp;').replace(/\"/g,'&quot;')}"></label>
   <label>Tutar*<input id="ceAmount" inputmode="decimal" value="${Number(x.amount||0)}"></label>
   <label>Para Birimi<select id="ceCur"><option>IQD</option><option>USD</option><option>TRY</option></select></label>
   <label>Tarih<input id="ceDate" type="date" value="${String(x.expense_date||'').slice(0,10)}"></label>
   <label style="grid-column:1/-1">Açıklama<input id="ceNote" value="${String(x.note||'').replace(/&/g,'&amp;').replace(/\"/g,'&quot;')}"></label>
 </div><div style="margin-top:12px"><button class="btn green" onclick="saveCashExpenseEdit(${Number(x.id)})">Düzeltmeyi Kaydet</button></div>`,null);
 setTimeout(()=>{const e=document.getElementById('ceCur');if(e)e.value=(x.currency||'IQD')},0);
}
async function saveCashExpenseEdit(id){
 const body={document_no:(ceDoc.value||'').trim(),amount:parseMoney(ceAmount.value||0),currency:ceCur.value,expense_date:ceDate.value,note:(ceNote.value||'').trim()};
 if(!body.document_no)return alert('Fatura/Fiş No gerekli.');
 if(!(body.amount>0))return alert('Tutar 0’dan büyük olmalı.');
 if(!confirm('Bu harcama satırı düzeltilecek. Devam edilsin mi?'))return;
 try{await api('/api/cash-control/expense/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});closeM();await loadCashControl();}
 catch(e){alert(e.message)}
}

'''
if anchor not in s: raise RuntimeError('entry missing JS anchor not found')
s=s.replace(anchor,js+anchor,1)

p.write_text(s,encoding='utf-8')
print('patched cash expense edit permission v1')
