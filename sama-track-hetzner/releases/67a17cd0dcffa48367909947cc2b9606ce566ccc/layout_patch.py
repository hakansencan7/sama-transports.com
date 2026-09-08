import site_patch as patched
from fastapi import Request

# A4 print layout
html = patched.core.HTML
html = html.replace(
    '@page{size:A4 portrait;margin:10mm 15mm}',
    '@page{size:A4 portrait;margin:6mm 10mm 6mm 20mm}',
)
html = html.replace('.toolbar{width:150mm', '.toolbar{width:175mm')
html = html.replace(
    '.sheet{width:150mm;height:255mm;margin:10mm auto 8px;background:#fff;padding:2mm;',
    '.sheet{width:175mm;height:267mm;margin:6mm 10mm 8px 20mm;background:#fff;padding:2mm;',
)
html = html.replace(
    '.sheet{width:150mm;height:255mm;margin:0 auto;padding:1.5mm;',
    '.sheet{width:175mm;height:267mm;margin:0;padding:1.5mm;',
)
html = html.replace(
    '.sheet{width:150mm;height:267mm;margin:6mm 10mm 8px 25mm;background:#fff;padding:2mm;',
    '.sheet{width:175mm;height:267mm;margin:6mm 10mm 8px 20mm;background:#fff;padding:2mm;',
)
html = html.replace(
    '.sheet{width:150mm;height:267mm;margin:0;padding:1.5mm;',
    '.sheet{width:175mm;height:267mm;margin:0;padding:1.5mm;',
)

# Make ENTRY / return expenses visually distinct on the print form.
# Thick borders make the reviewed return-expense block obvious at a glance.
html = html.replace(
    '.entryExpense td{color:#b00020!important;font-weight:900}',
    '.entryExpense td{color:#b00020!important;font-weight:900;border-top:2px solid #111!important;border-bottom:2px solid #111!important}.entryExpense td:first-child{border-left:2px solid #111!important}.entryExpense td:last-child{border-right:2px solid #111!important}',
)

# Add a name field next to each existing return-extra amount field.
for slot in (1, 2, 3):
    old = (
        f'<div class="field"><label>Ekstra Gider {slot}</label><input id="gExtra{slot}" '
        f'type="text" inputmode="decimal" value="${{cx.entry_extra_expense_{slot}||0}}" oninput="calcEntry()"></div>'
    )
    name_list = '<datalist id="entryExpenseMemoryList"></datalist>' if slot == 1 else ''
    new = (
        f'<div class="field"><label>Ekstra Gider {slot} Adı</label><input id="gExtraName{slot}" '
        f'type="text" list="entryExpenseMemoryList" autocomplete="off" placeholder="Örn: Teker Tamiri" '
        f'onfocus="entryExpenseLoadTrip()" onchange="entryExpenseNameChanged({slot})">{name_list}</div>'
        f'<div class="field"><label>Ekstra Gider {slot} Tutarı</label><input id="gExtra{slot}" '
        f'type="text" inputmode="decimal" value="${{cx.entry_extra_expense_{slot}||0}}" '
        f'oninput="calcEntry()" onchange="entryExpenseSave({slot})"></div>'
    )
    html = html.replace(old, new)

# Helper functions are inserted into the application's existing JS block.
helper_js = r'''
let entryExpenseMemoryCache=[];
let entryExpenseTripLoaded='';

function entryExpenseNorm(v){return String(v||'').trim().toLocaleLowerCase('tr-TR');}

async function entryExpenseLoadMemory(){
  try{
    const rows=await api('/api/entry-expense-memory');
    entryExpenseMemoryCache=Array.isArray(rows)?rows:[];
    const dl=document.getElementById('entryExpenseMemoryList');
    if(dl){
      dl.innerHTML=entryExpenseMemoryCache.map(x=>'<option value="'+esc(x.label||'')+'"></option>').join('');
    }
  }catch(_e){}
}

async function entryExpenseLoadTrip(){
  const scna=String((cx&&cx.scna)||'');
  if(!scna)return;
  await entryExpenseLoadMemory();
  if(entryExpenseTripLoaded===scna)return;
  entryExpenseTripLoaded=scna;
  try{
    const rows=await api('/api/entry-expense-labels/'+encodeURIComponent(scna));
    (rows||[]).forEach(x=>{
      const el=document.getElementById('gExtraName'+x.slot);
      if(el)el.value=x.label||'';
    });
  }catch(_e){}
}

async function entryExpenseSave(slot){
  const scna=String((cx&&cx.scna)||'');
  const nameEl=document.getElementById('gExtraName'+slot);
  const amountEl=document.getElementById('gExtra'+slot);
  if(!scna||!nameEl||!amountEl)return;
  const label=String(nameEl.value||'').trim();
  const amount=typeof parseMoney==='function'?parseMoney(amountEl.value||0):Number(amountEl.value||0);
  try{
    await api('/api/entry-expense-labels/'+encodeURIComponent(scna),{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({slot:slot,label:label,amount:amount})
    });
    await entryExpenseLoadMemory();
  }catch(_e){}
}

async function entryExpenseNameChanged(slot){
  await entryExpenseLoadMemory();
  const nameEl=document.getElementById('gExtraName'+slot);
  const amountEl=document.getElementById('gExtra'+slot);
  if(!nameEl||!amountEl)return;
  const hit=entryExpenseMemoryCache.find(x=>entryExpenseNorm(x.label)===entryExpenseNorm(nameEl.value));
  const current=typeof parseMoney==='function'?parseMoney(amountEl.value||0):Number(amountEl.value||0);
  if(hit && (!current || current===0) && Number(hit.last_amount||0)>0){
    amountEl.value=Number(hit.last_amount).toLocaleString('tr-TR');
    if(typeof calcEntry==='function')calcEntry();
  }
  await entryExpenseSave(slot);
}

'''
marker = 'async function openEntry(scna){'
if marker in html and 'entryExpenseMemoryCache' not in html:
    html = html.replace(marker, helper_js + marker, 1)

patched.core.HTML = html

# Additive persistent tables only. Existing trips/data are not replaced.
c = patched.core.db()
c.executescript('''
CREATE TABLE IF NOT EXISTS entry_expense_memory(
  label TEXT PRIMARY KEY COLLATE NOCASE,
  last_amount REAL DEFAULT 0,
  use_count INTEGER DEFAULT 0,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trip_entry_expense_labels(
  scna TEXT NOT NULL,
  slot INTEGER NOT NULL,
  label TEXT DEFAULT '',
  amount REAL DEFAULT 0,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(scna,slot)
);
''')
c.commit()
c.close()

@patched.app.get('/api/entry-expense-memory')
def entry_expense_memory():
    c=patched.core.db()
    try:
        rows=c.execute('''SELECT label,last_amount,use_count FROM entry_expense_memory
                          ORDER BY use_count DESC,updated_at DESC,label LIMIT 100''').fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()

@patched.app.get('/api/entry-expense-labels/{scna}')
def entry_expense_labels(scna:str):
    c=patched.core.db()
    try:
        rows=c.execute('''SELECT slot,label,amount FROM trip_entry_expense_labels
                          WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) ORDER BY slot''',(scna,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()

@patched.app.post('/api/entry-expense-labels/{scna}')
async def save_entry_expense_label(scna:str, request:Request):
    body=await request.json()
    slot=int(body.get('slot') or 0)
    if slot not in (1,2,3):
        return {'ok':False,'detail':'Geçersiz gider alanı'}
    label=' '.join(str(body.get('label') or '').strip().split())[:120]
    try:
        amount=float(body.get('amount') or 0)
    except Exception:
        amount=0
    c=patched.core.db()
    try:
        if label:
            c.execute('''INSERT INTO trip_entry_expense_labels(scna,slot,label,amount,updated_at)
                         VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(scna,slot) DO UPDATE SET
                           label=excluded.label,amount=excluded.amount,updated_at=CURRENT_TIMESTAMP''',
                      (str(scna).strip(),slot,label,amount))
            c.execute('''INSERT INTO entry_expense_memory(label,last_amount,use_count,updated_at)
                         VALUES(?,?,1,CURRENT_TIMESTAMP)
                         ON CONFLICT(label) DO UPDATE SET
                           last_amount=excluded.last_amount,
                           use_count=entry_expense_memory.use_count+1,
                           updated_at=CURRENT_TIMESTAMP''',(label,amount))
        else:
            c.execute('''DELETE FROM trip_entry_expense_labels
                         WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) AND slot=?''',(scna,slot))
        c.commit()
        return {'ok':True}
    finally:
        c.close()

# Replace the already-registered print-entry endpoint call without registering
# a duplicate route. This lets the print form show the saved expense names.
def _named_print_entry_expenses(scna: str):
    key=str(scna or '').strip()
    c=patched.core.db()
    try:
        trip=c.execute('''SELECT entry_extra_expense_1,entry_extra_expense_2,entry_extra_expense_3,entry_note
                          FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',(key,)).fetchone()
        fuels=c.execute('''SELECT liters,total,note FROM fuel_purchases
                           WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) ORDER BY id''',(key,)).fetchall()
        labels={int(r['slot']):str(r['label'] or '').strip() for r in c.execute(
            '''SELECT slot,label FROM trip_entry_expense_labels
               WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',(key,)).fetchall()}

        rows=[]
        road_total=sum(float(r['total'] or 0) for r in fuels)
        road_liters=sum(float(r['liters'] or 0) for r in fuels)
        fuel_notes=[str(r['note'] or '').strip() for r in fuels if str(r['note'] or '').strip()]
        if road_total or road_liters or fuel_notes:
            rows.append([
                '10','Road Fuel Expense (ENTRY)','مصاريف وقود الطريق - الدخول',
                f'{road_liters:g} L' if road_liters else '-',road_total,'entryExpense',
                '; '.join(dict.fromkeys(fuel_notes)) or 'Fuel purchased during trip'
            ])

        if trip:
            entry_note=str(trip['entry_note'] or '').strip()
            extras=[float(trip['entry_extra_expense_1'] or 0),float(trip['entry_extra_expense_2'] or 0),float(trip['entry_extra_expense_3'] or 0)]
            no=11
            for idx,amount in enumerate(extras,1):
                if amount:
                    saved_name=labels.get(idx,'').strip()
                    title=saved_name or f'Entry Extra Expense {idx}'
                    rows.append([
                        str(no),title,f'مصاريف دخول إضافية {idx}','-',amount,'entryExpense',entry_note
                    ])
                    no+=1
        return {'ok':True,'rows':rows}
    finally:
        c.close()

for route in patched.app.routes:
    if getattr(route,'path',None)=='/api/print-entry-expenses/{scna}' and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint=_named_print_entry_expenses
        if getattr(route,'dependant',None) is not None:
            route.dependant.call=_named_print_entry_expenses
        break

app = patched.app
