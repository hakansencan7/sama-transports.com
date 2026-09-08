import re
from fastapi import Request
import entry_fixed_expenses_patch as base

app = base.app
core = base.core
html = core.HTML

# Two free-form OTHER expenses live beside the fixed WEIGHBRIDGE/PARKING/WAITING lines.
c = core.db()
core.addcol(c, 'trips', 'entry_other_expense_1', 'REAL DEFAULT 0')
core.addcol(c, 'trips', 'entry_other_expense_2', 'REAL DEFAULT 0')
core.addcol(c, 'trips', 'entry_other_note_1', "TEXT DEFAULT ''")
core.addcol(c, 'trips', 'entry_other_note_2', "TEXT DEFAULT ''")
c.commit()
c.close()

@app.get('/api/trips/{scna}/entry-other-expenses')
def get_entry_other_expenses(scna: str):
    key = str(scna or '').strip()
    c = core.db()
    try:
        row = c.execute('''SELECT entry_other_expense_1,entry_other_expense_2,
                                  entry_other_note_1,entry_other_note_2
                           FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (key,)).fetchone()
        if not row:
            return []
        return [
            {'slot': 1, 'amount': float(row['entry_other_expense_1'] or 0), 'description': str(row['entry_other_note_1'] or '')},
            {'slot': 2, 'amount': float(row['entry_other_expense_2'] or 0), 'description': str(row['entry_other_note_2'] or '')},
        ]
    finally:
        c.close()

@app.post('/api/trips/{scna}/entry-other-expenses')
async def save_entry_other_expense(scna: str, request: Request):
    body = await request.json()
    slot = int(body.get('slot') or 0)
    if slot not in (1, 2):
        return {'ok': False, 'detail': 'Geçersiz OTHER kalemi.'}
    try:
        amount = max(float(body.get('amount') or 0), 0)
    except Exception:
        return {'ok': False, 'detail': 'OTHER tutarı hatalı.'}
    description = ' '.join(str(body.get('description') or '').strip().split())[:220]
    key = str(scna or '').strip()
    c = core.db()
    try:
        c.execute(f'''UPDATE trips
                      SET entry_other_expense_{slot}=?, entry_other_note_{slot}=?, updated_at=CURRENT_TIMESTAMP
                      WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (amount, description, key))
        c.commit()
    finally:
        c.close()
    return {'ok': True, 'slot': slot, 'amount': amount, 'description': description}

other_block = r'''
<div class="entry-other-wrap" id="entryOtherWrap">
  <div class="entry-other-head">OTHER / DİĞER GİDERLER <span>AMOUNT + DESCRIPTION</span></div>
  <div class="entry-other-row">
    <label>OTHER / DİĞER 1 - TUTAR / AMOUNT<input id="entryOtherAmount1" type="text" inputmode="decimal" value="0" oninput="entryOtherRecalc(false);entryOtherScheduleSave(1)" onchange="entryOtherSave(1)"></label>
    <label>AÇIKLAMA / DESCRIPTION<input id="entryOtherNote1" type="text" maxlength="220" placeholder="Örn: Araba yolda yağ aldı / Oil purchased on road" oninput="entryOtherRecalc(false);entryOtherScheduleSave(1)" onchange="entryOtherSave(1)"></label>
  </div>
  <div class="entry-other-row">
    <label>OTHER / DİĞER 2 - TUTAR / AMOUNT<input id="entryOtherAmount2" type="text" inputmode="decimal" value="0" oninput="entryOtherRecalc(false);entryOtherScheduleSave(2)" onchange="entryOtherSave(2)"></label>
    <label>AÇIKLAMA / DESCRIPTION<input id="entryOtherNote2" type="text" maxlength="220" placeholder="Örn: Lastik tamiri / Tyre repair" oninput="entryOtherRecalc(false);entryOtherScheduleSave(2)" onchange="entryOtherSave(2)"></label>
  </div>
</div>
'''
if 'id="entryOtherWrap"' not in html:
    pattern = r'(<input id="gExtra3" type="hidden"[^>]*>\s*</div>)'
    html, other_inserted = re.subn(pattern, lambda m: m.group(1) + other_block, html, count=1, flags=re.S)
else:
    other_inserted = 0

css = r'''
.entry-other-wrap{border:2px solid #d7a51b;border-radius:14px;padding:12px;margin:10px 0;background:#fffaf0}.entry-other-head{display:flex;justify-content:space-between;gap:10px;font-size:13px;font-weight:950;margin-bottom:9px}.entry-other-head span{font-size:10px;color:#79611b}.entry-other-row{display:grid;grid-template-columns:180px minmax(240px,1fr);gap:9px;margin-top:8px}.entry-other-row label{font-size:10px;font-weight:900;color:#526274}.entry-other-row input{width:100%;margin-top:5px}@media(max-width:800px){.entry-other-row{grid-template-columns:1fr}}
'''
if '</style>' in html and '.entry-other-wrap{' not in html:
    html = html.replace('</style>', css + '</style>', 1)

helper = r'''
let entryOtherLoadedScna='';
let entryOtherSaveTimers={};
function entryOtherNum(v){return typeof fixedEntryNum==='function'?fixedEntryNum(v):Number(v||0)||0;}
function entryOtherFmt(v){return typeof fixedEntryFmt==='function'?fixedEntryFmt(v):Number(v||0).toLocaleString('tr-TR');}
function entryOtherTotal(){return entryOtherNum(document.getElementById('entryOtherAmount1')?.value||0)+entryOtherNum(document.getElementById('entryOtherAmount2')?.value||0);}
function entryOtherRecalc(runCalc=true){
  if(runCalc && typeof calcEntry==='function')calcEntry();
  if(typeof fixedEntryRefreshSummary==='function')fixedEntryRefreshSummary();
}
function entryOtherScheduleSave(slot){clearTimeout(entryOtherSaveTimers[slot]);entryOtherSaveTimers[slot]=setTimeout(()=>entryOtherSave(slot),450);}
async function entryOtherSave(slot){
  const scna=String((window.cx&&cx.scna)||'').trim();if(!scna)return;
  const amount=entryOtherNum(document.getElementById('entryOtherAmount'+slot)?.value||0);
  const description=String(document.getElementById('entryOtherNote'+slot)?.value||'').trim();
  try{await api('/api/trips/'+encodeURIComponent(scna)+'/entry-other-expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot,amount,description})});}catch(_e){}
  entryOtherRecalc(true);
}
async function entryOtherLoad(){
  const scna=String((window.cx&&cx.scna)||'').trim();
  if(!scna||!document.getElementById('entryOtherAmount1')||entryOtherLoadedScna===scna)return;
  entryOtherLoadedScna=scna;
  try{
    const rows=await api('/api/trips/'+encodeURIComponent(scna)+'/entry-other-expenses');
    (rows||[]).forEach(x=>{
      const a=document.getElementById('entryOtherAmount'+x.slot);const n=document.getElementById('entryOtherNote'+x.slot);
      if(a)a.value=entryOtherFmt(x.amount||0);if(n)n.value=x.description||'';
    });
  }catch(_e){}
  if(typeof calcEntry==='function')calcEntry();
  if(typeof fixedEntryRefreshSummary==='function')fixedEntryRefreshSummary();
}
setInterval(()=>{if(document.getElementById('entryOtherAmount1'))entryOtherLoad();else entryOtherLoadedScna='';},500);
'''
marker = 'async function openEntry(scna){'
js_inserted = 0
if marker in html and 'function entryOtherTotal' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)
    js_inserted = 1

old_extra = '''  let extra=\n    parseMoney(gExtra1.value)+\n    parseMoney(gExtra2.value)+\n    parseMoney(gExtra3.value);'''
new_extra = '''  let extra=\n    parseMoney(gExtra1.value)+\n    parseMoney(gExtra2.value)+\n    parseMoney(gExtra3.value)+\n    (typeof entryOtherTotal==='function'?entryOtherTotal():0);'''
html = html.replace(old_extra, new_extra, 1)

summary_anchor = "    '<div class=\"sr\"><span>BEKLEME / WAITING</span><b id=\"sumFixed3\">0</b></div>'+"
summary_add = summary_anchor + "\n    '<div class=\"sr\"><span>OTHER / DİĞER 1</span><b id=\"sumOther1\">0</b></div>'+\n    '<div class=\"sr\"><span>OTHER / DİĞER 2</span><b id=\"sumOther2\">0</b></div>'+"
if summary_anchor in html and 'id="sumOther1"' not in html:
    html = html.replace(summary_anchor, summary_add, 1)

summary_refresh_anchor = "  const a=document.getElementById('sumFixedAll');if(a)a.textContent=fixedEntryFmt(all);"
summary_refresh_add = summary_refresh_anchor + "\n  const o1=document.getElementById('sumOther1');if(o1)o1.textContent=fixedEntryFmt(typeof entryOtherNum==='function'?entryOtherNum(document.getElementById('entryOtherAmount1')?.value||0):0);\n  const o2=document.getElementById('sumOther2');if(o2)o2.textContent=fixedEntryFmt(typeof entryOtherNum==='function'?entryOtherNum(document.getElementById('entryOtherAmount2')?.value||0):0);"
if summary_refresh_anchor in html and "getElementById('sumOther1')" not in html:
    html = html.replace(summary_refresh_anchor, summary_refresh_add, 1)

_original_tq = core.tq
def _tq_with_entry_other():
    sql = _original_tq()
    needle = 't.entry_extra_expense_3'
    addon = "t.entry_extra_expense_3 + COALESCE(t.entry_other_expense_1,0) + COALESCE(t.entry_other_expense_2,0)"
    return sql.replace(needle, addon)
core.tq = _tq_with_entry_other

# Single authoritative print builder. It is installed on BOTH the legacy and V2
# paths, so whichever URL the browser currently has will render the same data.
def _itemized_entry_print(scna: str):
    key = str(scna or '').strip()
    c = core.db()
    try:
        trip = c.execute('''SELECT entry_extra_expense_1,entry_extra_expense_2,entry_extra_expense_3,
                                  entry_other_expense_1,entry_other_expense_2,
                                  entry_other_note_1,entry_other_note_2,entry_note
                           FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (key,)).fetchone()
        fuels = c.execute('''SELECT liters,total,note FROM fuel_purchases
                             WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) ORDER BY id''', (key,)).fetchall()
        fixed_rows = c.execute('''SELECT slot,code,qty,unit_price,total FROM trip_entry_fixed_expenses
                                  WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) ORDER BY slot''', (key,)).fetchall()
        fixed = {int(r['slot']): dict(r) for r in fixed_rows}
        rows=[]
        road_total=sum(float(r['total'] or 0) for r in fuels)
        road_liters=sum(float(r['liters'] or 0) for r in fuels)
        fuel_notes=[str(r['note'] or '').strip() for r in fuels if str(r['note'] or '').strip()]
        if road_total or road_liters or fuel_notes:
            rows.append(['','ROAD FUEL / YOLDA MAZOT','وقود الطريق',f'{road_liters:g} L' if road_liters else '-',road_total,'entryExpense','; '.join(dict.fromkeys(fuel_notes))])

        fixed_labels={
            1:('KANTAR / WEIGHBRIDGE','الميزان','PCS'),
            2:('PARK / PARKING','موقف','DAY'),
            3:('BEKLEME / WAITING','انتظار','DAY'),
        }
        if trip:
            for slot in (1,2,3):
                meta=fixed.get(slot) or {}
                stored_total=float(trip[f'entry_extra_expense_{slot}'] or 0)
                total=float(meta.get('total') or stored_total or 0)
                qty=float(meta.get('qty') or 0)
                price=float(meta.get('unit_price') or 0)
                if not (total or qty or price):
                    continue
                en,ar,unit=fixed_labels[slot]
                qty_text=f'{qty:g} {unit} x {price:g}' if (qty or price) else '-'
                rows.append(['',en,ar,qty_text,total,'entryExpense',''])

            for slot in (1,2):
                amount=float(trip[f'entry_other_expense_{slot}'] or 0)
                note=str(trip[f'entry_other_note_{slot}'] or '').strip()
                if amount or note:
                    rows.append(['',f'OTHER / DİĞER {slot}','أخرى','-',amount,'entryExpense',note])
        return {'ok':True,'rows':rows}
    finally:
        c.close()

@app.get('/api/print-entry-expenses-v2/{scna}')
def print_entry_expenses_v2(scna: str):
    return _itemized_entry_print(scna)

# Override the old print endpoint too. This is the key fix for old browser/template
# versions that were still producing "Return Extra Expense 1/2/3".
patched_routes=0
for route in app.routes:
    if getattr(route,'path',None) in ('/api/print-entry-expenses/{scna}','/api/print-entry-expenses-v2/{scna}') and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint=_itemized_entry_print
        if getattr(route,'dependant',None) is not None:
            route.dependant.call=_itemized_entry_print
        patched_routes+=1

# Normalize print JS to the V2 URL when possible, but route override above makes
# this optional rather than brittle.
html = html.replace("/api/print-entry-expenses/'+encodeURIComponent(scna)", "/api/print-entry-expenses-v2/'+encodeURIComponent(scna)")

core.HTML = html
print(f'[SAMA] Entry OTHER + itemized print V3 active: other_ui={other_inserted}, js={js_inserted}, routes={patched_routes}')
