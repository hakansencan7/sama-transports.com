from pathlib import Path
p=Path('app.py'); s=p.read_text(encoding='utf-8')
MARK='# SAMA_CASH_CONTROL_V1'
if MARK in s:
 print('already patched'); raise SystemExit(0)
BACKEND=r'''
# SAMA_CASH_CONTROL_V1
class CashExpenseIn(BaseModel):
    document_no: str=''
    amount: float=0
    currency: str='IQD'
    note: str=''
    expense_date: str=''
class CashCountIn(BaseModel):
    business_date: str=''
    currency: str='IQD'
    opening_amount: float=0
    cash_in: float=0
    actual_amount: float=0
    note: str=''

def _ensure_cash_control(c):
    c.execute("""CREATE TABLE IF NOT EXISTS cash_daily_expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,document_no TEXT NOT NULL DEFAULT '',amount REAL NOT NULL DEFAULT 0,currency TEXT NOT NULL DEFAULT 'IQD',note TEXT DEFAULT '',expense_date TEXT NOT NULL DEFAULT '',created_at DATETIME DEFAULT CURRENT_TIMESTAMP,created_by TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS cash_daily_counts(id INTEGER PRIMARY KEY AUTOINCREMENT,business_date TEXT NOT NULL,currency TEXT NOT NULL DEFAULT 'IQD',opening_amount REAL NOT NULL DEFAULT 0,cash_in REAL NOT NULL DEFAULT 0,actual_amount REAL NOT NULL DEFAULT 0,note TEXT DEFAULT '',created_at DATETIME DEFAULT CURRENT_TIMESTAMP,created_by TEXT DEFAULT '')""")
    c.commit()

@app.get('/api/cash-control')
def cash_control_summary(business_date:str='',currency:str='IQD'):
    day=(business_date or datetime.now().strftime('%Y-%m-%d')).strip(); cur=(currency or 'IQD').upper().strip()
    c=db(); _ensure_cash_control(c); _ensure_advances(c)
    last=c.execute("SELECT * FROM cash_daily_counts WHERE business_date=? AND currency=? ORDER BY id DESC LIMIT 1",(day,cur)).fetchone()
    opening=float(last['opening_amount'] or 0) if last else 0; cash_in=float(last['cash_in'] or 0) if last else 0; actual=float(last['actual_amount'] or 0) if last else 0
    advances=float(c.execute("SELECT COALESCE(SUM(amount),0) FROM cash_advances WHERE currency=? AND DATE(created_at)=?",(cur,day)).fetchone()[0] or 0)
    expenses=float(c.execute("SELECT COALESCE(SUM(amount),0) FROM cash_daily_expenses WHERE currency=? AND expense_date=?",(cur,day)).fetchone()[0] or 0)
    rows=[dict(r) for r in c.execute("SELECT * FROM cash_daily_expenses WHERE currency=? AND expense_date=? ORDER BY id DESC",(cur,day))]
    expected=opening+cash_in-advances-expenses; diff=actual-expected
    c.close(); return {'business_date':day,'currency':cur,'opening_amount':opening,'cash_in':cash_in,'advance_out':advances,'expense_out':expenses,'expected_amount':expected,'actual_amount':actual,'difference':diff,'expenses':rows}

@app.post('/api/cash-control/expense')
def cash_control_expense(x:CashExpenseIn):
    doc=(x.document_no or '').strip(); amt=float(x.amount or 0); cur=(x.currency or 'IQD').upper().strip(); day=(x.expense_date or '').strip() or datetime.now().strftime('%Y-%m-%d')
    if not doc: raise HTTPException(400,'Fiş/Fatura numarası zorunlu.')
    if amt<=0: raise HTTPException(400,'Tutar zorunlu ve 0 dan büyük olmalı.')
    c=db(); _ensure_cash_control(c); user=CURRENT_AUTH_USER.get() or {}; username=user.get('username','') if isinstance(user,dict) else ''
    c.execute("INSERT INTO cash_daily_expenses(document_no,amount,currency,note,expense_date,created_at,created_by) VALUES(?,?,?,?,?,DATETIME('now','localtime'),?)",(doc,amt,cur,(x.note or '').strip(),day,username)); c.commit(); c.close()
    return {'ok':True}

@app.post('/api/cash-control/count')
def cash_control_count(x:CashCountIn):
    day=(x.business_date or '').strip() or datetime.now().strftime('%Y-%m-%d'); cur=(x.currency or 'IQD').upper().strip()
    c=db(); _ensure_cash_control(c); user=CURRENT_AUTH_USER.get() or {}; username=user.get('username','') if isinstance(user,dict) else ''
    c.execute("INSERT INTO cash_daily_counts(business_date,currency,opening_amount,cash_in,actual_amount,note,created_at,created_by) VALUES(?,?,?,?,?,?,DATETIME('now','localtime'),?)",(day,cur,float(x.opening_amount or 0),float(x.cash_in or 0),float(x.actual_amount or 0),(x.note or '').strip(),username)); c.commit(); c.close()
    return {'ok':True}
'''
idx=s.find('\n\nHTML = r"""')
if idx<0: raise RuntimeError('HTML anchor missing')
s=s[:idx]+BACKEND+s[idx:]
nav='''    <button onclick="show('advances',this)">Avans Takip</button>'''
if nav not in s: raise RuntimeError('finance nav missing')
s=s.replace(nav,nav+'''\n    <button onclick="show('cashcontrol',this)">Günlük Kasa</button>''',1)
panel=r'''
<section id="cashcontrol" class="panel">
<div class="filterbar"><b>Günlük Kasa Kontrolü</b><input id="cashDay" type="date" onchange="loadCashControl()"><select id="cashCur" onchange="loadCashControl()"><option>IQD</option><option>USD</option><option>TRY</option></select><button class="btn primary" onclick="openCashCount()">Kasa Tutarı Gir / Hesapla</button><button class="btn secondary" onclick="cashAddExpenseRow()">+ Harcama Satırı</button><button class="btn secondary" onclick="for(let i=0;i<10;i++)cashAddExpenseRow()">+ 10 Satır</button></div>
<div class="cards"><div class="card">Gün Başı Kasa<b id="cashOpening">0</b></div><div class="card">Nakit Giriş<b id="cashIn">0</b></div><div class="card">Verilen Avans<b id="cashAdvance">0</b></div><div class="card">Günlük Harcama<b id="cashExpense">0</b></div><div class="card">Beklenen Kasa<b id="cashExpected">0</b></div><div class="card">Fiili Kasa<b id="cashActual">0</b></div><div class="card">Kasa Farkı<b id="cashDiff">0</b></div></div>
<div class="section-note">Doğrudan kasadan ödenen fiş/faturaları girin. Avans karşılığı getirilen belgeleri buraya tekrar girmeyin; avans zaten kasadan çıkış sayılır.</div>
<div class="table"><table><thead><tr><th>Tarih (boşsa bugün)</th><th>Fiş/Fatura No *</th><th>Tutar *</th><th>Açıklama</th><th></th></tr></thead><tbody id="cashExpenseEntry"></tbody></table></div><div style="margin:10px 0"><button class="btn green" onclick="saveCashExpenses()">Harcama Satırlarını Kaydet</button></div>
<div class="table"><table><thead><tr><th>Tarih</th><th>Fiş/Fatura No</th><th>Tutar</th><th>Açıklama</th><th>Giren</th></tr></thead><tbody id="cashExpenseHistory"></tbody></table></div>
</section>
'''
needle='<section id="deleted" class="panel">'
if needle not in s: raise RuntimeError('panel anchor missing')
s=s.replace(needle,panel+'\n'+needle,1)
s=s.replace("  if(id==='advances') loadAdvances();","  if(id==='advances') loadAdvances();\n  if(id==='cashcontrol') loadCashControl();",1)
JS=r'''
let cashSummary=null;
function cashToday(){return new Date().toISOString().slice(0,10)}
async function loadCashControl(){
 if(!cashDay.value)cashDay.value=cashToday(); cashSummary=await api('/api/cash-control?business_date='+encodeURIComponent(cashDay.value)+'&currency='+encodeURIComponent(cashCur.value));
 const c=cashSummary.currency; cashOpening.innerText=money(cashSummary.opening_amount)+' '+c; cashIn.innerText=money(cashSummary.cash_in)+' '+c; cashAdvance.innerText=money(cashSummary.advance_out)+' '+c; cashExpense.innerText=money(cashSummary.expense_out)+' '+c; cashExpected.innerText=money(cashSummary.expected_amount)+' '+c; cashActual.innerText=money(cashSummary.actual_amount)+' '+c;
 const d=Number(cashSummary.difference||0); cashDiff.innerText=(d<0?'AÇIK ':'FAZLA ')+money(Math.abs(d))+' '+c; cashDiff.style.color=d<0?'#ef4444':(d>0?'#22c55e':'inherit');
 cashExpenseHistory.innerHTML=(cashSummary.expenses||[]).map(x=>`<tr><td>${x.expense_date||''}</td><td>${x.document_no||''}</td><td>${money(x.amount)} ${x.currency||''}</td><td>${x.note||''}</td><td>${x.created_by||''}</td></tr>`).join('');
}
function cashAddExpenseRow(){
 cashExpenseEntry.insertAdjacentHTML('beforeend',`<tr><td><input class="ceDate" type="date" title="Boşsa bugün"></td><td><input class="ceDoc" placeholder="Fiş/Fatura No *"></td><td><input class="ceAmt" type="number" min="0" step="1" placeholder="Tutar *"></td><td><input class="ceNote" placeholder="Açıklama (opsiyonel)"></td><td><button class="btn secondary" onclick="this.closest('tr').remove()">Sil</button></td></tr>`);
}
async function saveCashExpenses(){
 const rows=[...cashExpenseEntry.querySelectorAll('tr')]; if(!rows.length)return alert('Harcama satırı girin.');
 try{for(let i=0;i<rows.length;i++){const tr=rows[i],doc=tr.querySelector('.ceDoc').value.trim(),amt=Number(tr.querySelector('.ceAmt').value||0);if(!doc)throw new Error((i+1)+'. satırda fiş/fatura numarası zorunlu.');if(amt<=0)throw new Error((i+1)+'. satırda tutar zorunlu.');await api('/api/cash-control/expense',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({document_no:doc,amount:amt,currency:cashCur.value,note:tr.querySelector('.ceNote').value,expense_date:tr.querySelector('.ceDate').value})});} cashExpenseEntry.innerHTML=''; await loadCashControl(); alert(rows.length+' harcama kaydedildi.');}catch(e){alert(e.message)}
}
function openCashCount(){
 const x=cashSummary||{opening_amount:0,cash_in:0,actual_amount:0}; openM('Kasa Tutarı / Gün Sonu Kontrolü',`<div class="grid"><div class="field"><label>Tarih</label><input id="ccDay" type="date" value="${cashDay.value||cashToday()}"></div><div class="field"><label>Para Birimi</label><input value="${cashCur.value}" disabled></div><div class="field"><label>Gün Başı Kasa</label><input id="ccOpen" type="number" value="${Number(x.opening_amount||0)}"></div><div class="field"><label>Gün İçindeki Nakit Giriş</label><input id="ccIn" type="number" value="${Number(x.cash_in||0)}"></div><div class="field wide"><label>Fiilen Saydığım Kasa</label><input id="ccActual" type="number" value="${Number(x.actual_amount||0)}"></div><div class="field wide"><label>Not</label><input id="ccNote"></div></div>`,async()=>{try{await api('/api/cash-control/count',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({business_date:ccDay.value,currency:cashCur.value,opening_amount:Number(ccOpen.value||0),cash_in:Number(ccIn.value||0),actual_amount:Number(ccActual.value||0),note:ccNote.value})});cashDay.value=ccDay.value;closeM();await loadCashControl();}catch(e){alert(e.message)}});
}
'''
anchor='let advanceRows=[];'
if anchor not in s: raise RuntimeError('JS anchor missing')
s=s.replace(anchor,JS+'\n'+anchor,1)
p.write_text(s,encoding='utf-8'); print('patched cash control')
