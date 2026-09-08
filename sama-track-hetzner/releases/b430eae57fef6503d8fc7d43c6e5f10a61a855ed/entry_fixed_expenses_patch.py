import re
from fastapi import Request
import dashboard_remove_driver_diff_patch as base

app = base.app
core = base.core
html = core.HTML

FIXED = {
    1: ('WEIGHBRIDGE', 'KANTAR / WEIGHBRIDGE', 'ADET / PCS'),
    2: ('PARKING', 'PARK / PARKING', 'GÜN / DAY'),
    3: ('WAITING', 'BEKLEME / WAITING', 'GÜN / DAY'),
}

# Persistent quantity/unit price metadata. Existing trip totals remain in the
# established entry_extra_expense_1..3 columns so all old calculations keep working.
c = core.db()
c.execute('''
CREATE TABLE IF NOT EXISTS trip_entry_fixed_expenses(
  scna TEXT NOT NULL,
  slot INTEGER NOT NULL,
  code TEXT NOT NULL,
  qty REAL DEFAULT 0,
  unit_price REAL DEFAULT 0,
  total REAL DEFAULT 0,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(scna,slot)
)
''')
c.commit()
c.close()

@app.get('/api/trips/{scna}/entry-fixed-expenses')
def get_entry_fixed_expenses(scna: str):
    c = core.db()
    try:
        rows = c.execute('''SELECT slot,code,qty,unit_price,total
                            FROM trip_entry_fixed_expenses
                            WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))
                            ORDER BY slot''', (str(scna).strip(),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()

@app.post('/api/trips/{scna}/entry-fixed-expenses')
async def save_entry_fixed_expense(scna: str, request: Request):
    body = await request.json()
    slot = int(body.get('slot') or 0)
    if slot not in FIXED:
        return {'ok': False, 'detail': 'Geçersiz sabit gider kalemi.'}
    try:
        qty = max(float(body.get('qty') or 0), 0)
        unit_price = max(float(body.get('unit_price') or 0), 0)
    except Exception:
        return {'ok': False, 'detail': 'Miktar veya birim fiyat hatalı.'}
    total = qty * unit_price
    code, label, _unit = FIXED[slot]
    key = str(scna or '').strip()
    c = core.db()
    try:
        c.execute('''INSERT INTO trip_entry_fixed_expenses(scna,slot,code,qty,unit_price,total,updated_at)
                     VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(scna,slot) DO UPDATE SET
                       code=excluded.code,qty=excluded.qty,unit_price=excluded.unit_price,
                       total=excluded.total,updated_at=CURRENT_TIMESTAMP''',
                  (key, slot, code, qty, unit_price, total))
        # Keep the existing settlement engine and print logic intact.
        c.execute(f'''UPDATE trips SET entry_extra_expense_{slot}=?,updated_at=CURRENT_TIMESTAMP
                      WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (total, key))
        c.execute('''INSERT INTO trip_entry_expense_labels(scna,slot,label,amount,updated_at)
                     VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(scna,slot) DO UPDATE SET
                       label=excluded.label,amount=excluded.amount,updated_at=CURRENT_TIMESTAMP''',
                  (key, slot, label, total))
        c.commit()
    finally:
        c.close()
    return {'ok': True, 'slot': slot, 'code': code, 'qty': qty, 'unit_price': unit_price, 'total': total}

# Replace the three free-name entry expense fields with fixed bilingual lines.
replaced = 0
for slot, (_code, label, unit) in FIXED.items():
    pattern = (
        rf'<div class="field"><label>Ekstra Gider {slot} Adı</label><input id="gExtraName{slot}".*?</div>'
        rf'<div class="field"><label>Ekstra Gider {slot} Tutarı</label><input id="gExtra{slot}".*?</div>'
    )
    block = f'''<div class="fixed-entry-expense" data-fixed-slot="{slot}">
  <div class="fixed-entry-title"><b>{label}</b><span>{unit}</span></div>
  <div class="fixed-entry-grid">
    <label>MİKTAR / QTY<input id="fixedQty{slot}" type="text" inputmode="decimal" value="0" oninput="fixedEntryRecalc({slot},false)" onchange="fixedEntryRecalc({slot},true)"></label>
    <label>BİRİM FİYAT / UNIT PRICE<input id="fixedPrice{slot}" type="text" inputmode="decimal" value="0" oninput="fixedEntryRecalc({slot},false)" onchange="fixedEntryRecalc({slot},true)"></label>
    <div class="fixed-entry-total">TOPLAM / TOTAL<strong id="fixedTotal{slot}">0</strong></div>
  </div>
  <input id="gExtraName{slot}" type="hidden" value="{label}">
  <input id="gExtra{slot}" type="hidden" value="${{cx.entry_extra_expense_{slot}||0}}">
</div>'''
    html, n = re.subn(pattern, block, html, count=1, flags=re.S)
    replaced += n

css = r'''
.fixed-entry-expense{border:1px solid #d6dde6;border-radius:14px;padding:12px;margin:8px 0;background:#fff}.fixed-entry-title{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:9px}.fixed-entry-title b{font-size:14px}.fixed-entry-title span{font-size:11px;font-weight:900;color:#526274;background:#edf2f7;border-radius:999px;padding:5px 8px}.fixed-entry-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;align-items:end}.fixed-entry-grid label{font-size:10px;font-weight:900;color:#526274}.fixed-entry-grid input{width:100%;margin-top:5px}.fixed-entry-total{border-radius:10px;background:#0f2942;color:#fff;padding:9px;font-size:10px;font-weight:900}.fixed-entry-total strong{display:block;font-size:17px;margin-top:4px}.sama-entry-sticky{position:fixed;right:18px;top:92px;width:285px;z-index:9000;background:#0d2134;color:#fff;border:1px solid #36536c;border-radius:16px;padding:13px;box-shadow:0 12px 32px #0004}.sama-entry-sticky h4{margin:0 0 9px;font-size:14px}.sama-entry-sticky .sr{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid #ffffff17;font-size:11px}.sama-entry-sticky .sr b{font-size:12px}.sama-entry-sticky .grand{font-size:13px;font-weight:950;border-top:2px solid #5d7488;margin-top:5px}.sama-entry-sticky .status{margin-top:9px;border-radius:10px;padding:9px;background:#17344f;font-size:11px;font-weight:900}.sama-entry-sticky .closex{float:right;border:0;background:transparent;color:#fff;font-size:17px;cursor:pointer}.sama-entry-summary-collapsed{display:none!important}@media(max-width:1100px){.sama-entry-sticky{position:sticky;top:6px;right:auto;width:100%;margin:7px 0 10px;z-index:40}.fixed-entry-grid{grid-template-columns:1fr 1fr}.fixed-entry-total{grid-column:1/3}}
'''
if '</style>' in html and '.fixed-entry-expense{' not in html:
    html = html.replace('</style>', css + '</style>', 1)

helper = r'''
const fixedEntryLabels={1:'KANTAR / WEIGHBRIDGE',2:'PARK / PARKING',3:'BEKLEME / WAITING'};
let fixedEntryLoadedScna='';
function fixedEntryNum(v){
  if(typeof parseMoney==='function') return Number(parseMoney(v||0)||0);
  let s=String(v||'').trim().replace(/\s/g,'');
  if(/^\d{1,3}([.,]\d{3})+$/.test(s)) return Number(s.replace(/[.,]/g,''));
  return Number(s.replace(/\./g,'').replace(',','.'))||0;
}
function fixedEntryFmt(v){return Number(v||0).toLocaleString('tr-TR',{maximumFractionDigits:2});}
function fixedEntryEnsureSummary(){
  if(document.getElementById('samaEntryStickySummary'))return;
  const anchor=document.querySelector('[data-fixed-slot="1"]');
  if(!anchor)return;
  const box=document.createElement('aside');
  box.id='samaEntryStickySummary';box.className='sama-entry-sticky';
  box.innerHTML='<button type="button" class="closex" title="Kapat" onclick="this.parentElement.classList.toggle(\'sama-entry-summary-collapsed\')">×</button><h4>GİRİŞ ÖZETİ / ENTRY SUMMARY</h4>'+
    '<div class="sr"><span>KANTAR / WEIGHBRIDGE</span><b id="sumFixed1">0</b></div>'+
    '<div class="sr"><span>PARK / PARKING</span><b id="sumFixed2">0</b></div>'+
    '<div class="sr"><span>BEKLEME / WAITING</span><b id="sumFixed3">0</b></div>'+
    '<div class="sr grand"><span>SABİT GİDER / FIXED TOTAL</span><b id="sumFixedAll">0</b></div>'+
    '<div class="sr"><span>DÖNÜŞ GİDERİ / RETURN EXPENSE</span><b id="sumReturnSpend">0</b></div>'+
    '<div class="sr"><span>VERMESİ GEREKEN / SHOULD RETURN</span><b id="sumExpected">0</b></div>'+
    '<div class="sr"><span>GETİRİLEN / RETURNED CASH</span><b id="sumHand">0</b></div>'+
    '<div class="status" id="sumAccountState">HESAP / ACCOUNT: -</div>';
  anchor.parentElement.insertBefore(box,anchor);
}
function fixedEntryRefreshSummary(){
  fixedEntryEnsureSummary();
  let all=0;
  [1,2,3].forEach(slot=>{const v=fixedEntryNum(document.getElementById('gExtra'+slot)?.value||0);all+=v;const e=document.getElementById('sumFixed'+slot);if(e)e.textContent=fixedEntryFmt(v);});
  const a=document.getElementById('sumFixedAll');if(a)a.textContent=fixedEntryFmt(all);
  const rs=document.getElementById('sumReturnSpend');if(rs)rs.textContent=document.getElementById('gReturnSpend')?.textContent||'0';
  const ex=document.getElementById('sumExpected');if(ex)ex.textContent=document.getElementById('gExpected')?.textContent||'0';
  const ha=document.getElementById('sumHand');if(ha)ha.textContent=document.getElementById('gHandShow')?.textContent||'0';
  const st=document.getElementById('sumAccountState');if(st){const src=document.getElementById('gStatus');st.innerHTML='HESAP / ACCOUNT: '+(src?.innerHTML||'-');}
}
async function fixedEntrySave(slot){
  const scna=String((window.cx&&cx.scna)||'').trim();if(!scna)return;
  const qty=fixedEntryNum(document.getElementById('fixedQty'+slot)?.value||0);
  const unit_price=fixedEntryNum(document.getElementById('fixedPrice'+slot)?.value||0);
  try{await api('/api/trips/'+encodeURIComponent(scna)+'/entry-fixed-expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot,qty,unit_price})});}catch(_e){}
}
function fixedEntryRecalc(slot,save){
  const q=fixedEntryNum(document.getElementById('fixedQty'+slot)?.value||0);
  const p=fixedEntryNum(document.getElementById('fixedPrice'+slot)?.value||0);
  const total=q*p;
  const hidden=document.getElementById('gExtra'+slot);if(hidden)hidden.value=total;
  const totalEl=document.getElementById('fixedTotal'+slot);if(totalEl)totalEl.textContent=fixedEntryFmt(total);
  const nameEl=document.getElementById('gExtraName'+slot);if(nameEl)nameEl.value=fixedEntryLabels[slot]||'';
  if(typeof calcEntry==='function')calcEntry();
  fixedEntryRefreshSummary();
  if(save)fixedEntrySave(slot);
}
async function fixedEntryLoad(){
  const scna=String((window.cx&&cx.scna)||'').trim();
  if(!scna||!document.getElementById('fixedQty1')||fixedEntryLoadedScna===scna)return;
  fixedEntryLoadedScna=scna;fixedEntryEnsureSummary();
  try{
    const rows=await api('/api/trips/'+encodeURIComponent(scna)+'/entry-fixed-expenses');
    const by={};(rows||[]).forEach(x=>by[Number(x.slot)]=x);
    [1,2,3].forEach(slot=>{
      const x=by[slot];
      if(x){
        const q=document.getElementById('fixedQty'+slot);const p=document.getElementById('fixedPrice'+slot);
        if(q)q.value=fixedEntryFmt(x.qty);if(p)p.value=fixedEntryFmt(x.unit_price);
        const h=document.getElementById('gExtra'+slot);if(h)h.value=Number(x.total||0);
        const t=document.getElementById('fixedTotal'+slot);if(t)t.textContent=fixedEntryFmt(x.total);
      }else{
        const old=fixedEntryNum(document.getElementById('gExtra'+slot)?.value||0);
        const t=document.getElementById('fixedTotal'+slot);if(t)t.textContent=fixedEntryFmt(old);
      }
      const n=document.getElementById('gExtraName'+slot);if(n)n.value=fixedEntryLabels[slot]||'';
    });
  }catch(_e){}
  if(typeof calcEntry==='function')calcEntry();fixedEntryRefreshSummary();
}
setInterval(()=>{if(document.getElementById('fixedQty1'))fixedEntryLoad();else fixedEntryLoadedScna='';},500);
'''

marker = 'async function openEntry(scna){'
js_inserted = 0
if marker in html and 'function fixedEntryRecalc' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)
    js_inserted = 1

# Keep sticky values in sync with the established entry calculator.
needle = '  gDiff.innerText=money(diff);'
if needle in html and 'fixedEntryRefreshSummary();' in helper:
    html = html.replace(needle, needle + "\n  if(typeof fixedEntryRefreshSummary==='function')fixedEntryRefreshSummary();", 1)

core.HTML = html
print(f'[SAMA] Fixed entry expenses bilingual + sticky summary active: fields={replaced}, js={js_inserted}')
