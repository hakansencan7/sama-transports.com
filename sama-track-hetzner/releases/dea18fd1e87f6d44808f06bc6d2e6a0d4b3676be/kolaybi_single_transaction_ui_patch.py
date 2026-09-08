import re
from fastapi import HTTPException
import kolaybi_preview_diagnostic_patch as base

app = base.app
core = base.core
kdb = base.kdb
html = core.HTML

# One fixed KolayBi product mapping for the SALE side. The actual KolayBi identity
# is still the mapped product_id; the local label is only for our UI.
c = kdb()
try:
    c.execute('''INSERT OR IGNORE INTO products(code,name_tr,name_en,unit,is_active,note)
                 VALUES('SALE_FREIGHT','NAKLİYE HİZMETİ','FREIGHT SERVICE','KG',1,'SALE sabit ürün eşleştirmesi')''')
    c.commit()
finally:
    c.close()


def _norm(v):
    s = str(v or '').upper()
    s = s.replace('İ','I').replace('Ş','S').replace('Ğ','G').replace('Ü','U').replace('Ö','O').replace('Ç','C')
    return re.sub(r'[^A-Z0-9]+', '', s)


def _safe_contact_by_name(name: str):
    wanted = _norm(name)
    if not wanted:
        return None
    c = kdb()
    try:
        rows = [dict(r) for r in c.execute('SELECT * FROM associates WHERE is_active=1').fetchall()]
    finally:
        c.close()
    candidates = []
    for r in rows:
        if wanted in (_norm(r.get('name')), _norm(r.get('key'))):
            candidates.append(r)
    uniq = {}
    for r in candidates:
        cid = str(r.get('contact_id') or '').strip()
        if cid:
            uniq[cid] = r
    return next(iter(uniq.values())) if len(uniq) == 1 else None


def _product(code: str):
    c = kdb()
    try:
        r = c.execute('SELECT * FROM products WHERE UPPER(code)=UPPER(?) AND is_active=1',(code,)).fetchone()
        return dict(r) if r else {}
    finally:
        c.close()


@app.get('/api/kolaybi/single-preview/{scna}')
def kb_single_preview(scna: str):
    # PURCHASE uses the already tested expense engine.
    purchase = base.webmod.kolaybi_preview(scna)

    c = core.db()
    try:
        tr = c.execute('''SELECT t.*, COALESCE(cu.name,'') customer_name
                          FROM trips t LEFT JOIN customers cu ON cu.id=t.customer_id
                          WHERE UPPER(TRIM(t.scna))=UPPER(TRIM(?))''',(str(scna or '').strip(),)).fetchone()
        if not tr:
            raise HTTPException(status_code=404, detail='SCNA bulunamadı.')
        tr = dict(tr)
    finally:
        c.close()

    customer = str(tr.get('customer_name') or '').strip()
    sale_contact = _safe_contact_by_name(customer)
    sale_product = _product('SALE_FREIGHT')
    project = purchase.get('project') or {}

    basis = str(tr.get('freight_basis') or 'KG').strip().upper()
    net_kg = float(tr.get('net_kg') or 0)
    rate = float(tr.get('freight_rate') or 0)
    excel_amount = float(tr.get('excel_amount') or 0)
    # Prefer an imported authoritative amount when present. Otherwise use SAMA's
    # current shipment fields: KG = kg x rate, ADET = one shipment x rate.
    if excel_amount > 0:
        sale_total = excel_amount
        sale_qty = net_kg if basis == 'KG' and net_kg > 0 else 1
        sale_unit_price = sale_total / sale_qty if sale_qty else sale_total
        amount_source = 'EXCEL AMOUNT'
    elif basis == 'KG':
        sale_qty = net_kg
        sale_unit_price = rate
        sale_total = net_kg * rate
        amount_source = 'NET KG × FREIGHT RATE'
    else:
        sale_qty = 1
        sale_unit_price = rate
        sale_total = rate
        amount_source = 'ADET × FREIGHT RATE'

    sale_missing = []
    if not str(sale_product.get('product_id') or '').strip():
        sale_missing.append('PRODUCT ID: SALE_FREIGHT')
    if not sale_contact or not str(sale_contact.get('contact_id') or '').strip():
        sale_missing.append('CARİ / CONTACT ID')
    if not sale_contact or not str(sale_contact.get('address_id') or '').strip():
        sale_missing.append('ADDRESS ID')
    if not str(project.get('project_id') or '').strip():
        sale_missing.append('PROJECT ID')
    if sale_total <= 0:
        sale_missing.append('SATIŞ TUTARI')

    sale = {
        'scna': str(scna or '').strip(),
        'plate': str(tr.get('plate') or ''),
        'customer': customer,
        'contact': sale_contact,
        'project': project,
        'product': sale_product,
        'basis': basis,
        'quantity': sale_qty,
        'unit_price': sale_unit_price,
        'total': sale_total,
        'amount_source': amount_source,
        'missing_reasons': sale_missing,
        'ready': not sale_missing,
    }
    return {'ok': True, 'purchase': purchase, 'sale': sale}


# Insert a Toplu Ödeme-inspired SINGLE SCNA workspace. Existing master/config UI is
# kept, but hidden behind AYARLAR so thousands of rows no longer occupy the transaction page.
workspace = r'''
<div id="kbSingleWorkspace" class="calc" style="margin-bottom:14px">
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
    <button class="btn primary" onclick="kbMainMode('transaction')">TEK SCNA İŞLEM</button>
    <button class="btn secondary" onclick="kbMainMode('settings')">AYARLAR / EŞLEŞTİRMELER</button>
  </div>
  <div id="kbTransactionArea">
    <div class="filterbar" style="padding:0;margin-bottom:10px">
      <input id="kbSingleScna" placeholder="SCNA yaz..." style="max-width:260px">
      <button class="btn primary" onclick="kbLoadSingle()">SCNA KONTROLÜNÜ GETİR</button>
      <span id="kbSingleState" class="section-note"></span>
    </div>
    <div id="kbSingleResult" style="display:none;grid-template-columns:1fr 1fr;gap:12px">
      <div class="calc" style="margin:0">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><b>SATIN ALMA / PURCHASE</b><span id="kbPurchaseStatus"></span></div>
        <div id="kbPurchaseBody" style="margin-top:8px"></div>
      </div>
      <div class="calc" style="margin:0">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><b>SATIŞ / SALE</b><span id="kbSaleStatus"></span></div>
        <div id="kbSaleBody" style="margin-top:8px"></div>
      </div>
    </div>
  </div>
</div>'''

anchor = '<div class="kolaybi-previewbar">'
if anchor in html and 'id="kbSingleWorkspace"' not in html:
    html = html.replace(anchor, workspace + '\n  ' + anchor, 1)

helper = r'''
function kbSetDisplay(el,on,displayValue){if(el)el.style.display=on?(displayValue||''):'none';}
function kbMainMode(mode){
  const trans=document.getElementById('kbTransactionArea');
  kbSetDisplay(trans,mode==='transaction','');
  const oldPreview=document.querySelector('#kolaybi .kolaybi-previewbar');
  const oldBox=document.getElementById('kbPreviewBox');
  const tabs=document.querySelector('#kolaybi .kb-tabs');
  const conn=document.getElementById('kbBaseUrl');
  const connCard=conn?conn.closest('.calc'):null;
  const syncbar=document.querySelector('#kolaybi .kb-syncbar');
  kbSetDisplay(oldPreview,false); kbSetDisplay(oldBox,false);
  kbSetDisplay(connCard,mode==='settings',''); kbSetDisplay(syncbar,mode==='settings',''); kbSetDisplay(tabs,mode==='settings','');
  ['kbProducts','kbAssociates','kbProjects','kbTags'].forEach((id,idx)=>{const e=document.getElementById(id);kbSetDisplay(e,mode==='settings' && idx===0,'');});
  if(mode==='settings'){loadKolaybiMaster();kbLoadConnection();kbTab('products');}
}
async function kbLoadSingle(){
  const scna=String(document.getElementById('kbSingleScna')?.value||'').trim();
  const state=document.getElementById('kbSingleState');
  if(!scna){if(state)state.innerHTML='<span class="kb-missing">SCNA GİR</span>';return;}
  if(state)state.textContent='GETİRİLİYOR...';
  try{
    const x=await api('/api/kolaybi/single-preview/'+encodeURIComponent(scna));
    const p=x.purchase||{}, s=x.sale||{};
    const result=document.getElementById('kbSingleResult');if(result)result.style.display='grid';
    const ps=document.getElementById('kbPurchaseStatus'),ss=document.getElementById('kbSaleStatus');
    if(ps)ps.innerHTML=p.ready?'<span class="kb-ready">✓ HAZIR</span>':'<span class="kb-missing">EKSİK</span>';
    if(ss)ss.innerHTML=s.ready?'<span class="kb-ready">✓ HAZIR</span>':'<span class="kb-missing">EKSİK</span>';
    const pc=p.contact||{};
    const pitems=(p.items||[]).map(i=>`<div class="kb-item"><span><b>${kbEsc(i.name||i.code)}</b><br><small>Product ID: ${kbEsc(i.product_id||'-')}</small>${i.description?'<br><small>'+kbEsc(i.description)+'</small>':''}</span><span>${Number(i.total||0).toLocaleString('tr-TR')}</span></div>`).join('');
    const pb=document.getElementById('kbPurchaseBody');
    if(pb)pb.innerHTML=`<div><b>SCNA:</b> ${kbEsc(p.scna||scna)} | <b>PLATE:</b> ${kbEsc(p.plate||'-')}</div><div style="margin:5px 0"><b>Cari:</b> ${kbEsc(pc.name||p.customer||'-')} | ID: ${kbEsc(pc.contact_id||'-')} | Address: ${kbEsc(pc.address_id||'-')}</div>${(p.missing_reasons||[]).length?'<div class="kb-missing">'+kbEsc(p.missing_reasons.join(' | '))+'</div>':''}${pitems}${p.ready?`<button class="btn primary" style="margin-top:10px" onclick="kbSendScna('${kbEsc(p.scna||scna)}')">SATIN ALMA FATURASI GÖNDER</button>`:''}`;
    const sc=s.contact||{},sp=s.product||{};
    const sb=document.getElementById('kbSaleBody');
    if(sb)sb.innerHTML=`<div><b>Müşteri:</b> ${kbEsc(s.customer||'-')}</div><div><b>Contact ID:</b> ${kbEsc(sc.contact_id||'-')} | <b>Address ID:</b> ${kbEsc(sc.address_id||'-')}</div><div style="margin-top:8px"><b>Ürün:</b> ${kbEsc(sp.name_tr||sp.name_en||'NAKLİYE HİZMETİ')} | <b>Product ID:</b> ${kbEsc(sp.product_id||'-')}</div><div class="kb-item"><span>${kbEsc(s.basis||'KG')} | ${kbEsc(s.amount_source||'')}</span><span>${Number(s.quantity||0).toLocaleString('tr-TR')} × ${Number(s.unit_price||0).toLocaleString('tr-TR')} = <b>${Number(s.total||0).toLocaleString('tr-TR')}</b></span></div>${(s.missing_reasons||[]).length?'<div class="kb-missing">'+kbEsc(s.missing_reasons.join(' | '))+'</div>':''}<div class="section-note" style="margin-top:8px">SALE gönderim butonu, bu önizlemedeki tutar ve cari eşleşmesi doğrulandıktan sonra açılacak.</div>`;
    if(state)state.innerHTML='<span class="kb-ready">SCNA HAZIRLANDI</span>';
  }catch(e){if(state)state.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
'''
marker = 'async function kbPreview(){'
if marker in html and 'async function kbLoadSingle' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

# Keep huge reference tables useful but sane: no search = first 50 rows only.
old_render_start = 'function kbRenderMaster(){'
if old_render_start in html and 'kbLimitRows' not in html:
    limit_helper = r'''
function kbLimitRows(rows,searchId,fields){const q=String(document.getElementById(searchId)?.value||'').trim().toLocaleUpperCase('tr-TR');const src=rows||[];if(!q)return src.slice(0,50);return src.filter(x=>fields.some(f=>String(x?.[f]??'').toLocaleUpperCase('tr-TR').includes(q))).slice(0,200);}
'''
    html = html.replace(old_render_start, limit_helper + '\n' + old_render_start, 1)
    html = html.replace('(kbMaster.products||[]).map(', "kbLimitRows(kbMaster.products,'kbSearchProducts',['code','name_tr','name_en','product_id','unit']).map(", 1)
    html = html.replace('(kbMaster.associates||[]).map(', "kbLimitRows(kbMaster.associates,'kbSearchAssociates',['key','name','plate','contact_id','address_id']).map(", 1)
    html = html.replace('(kbMaster.projects||[]).map(', "kbLimitRows(kbMaster.projects,'kbSearchProjects',['code','name','project_id']).map(", 1)
    html = html.replace('(kbMaster.tags||[]).map(', "kbLimitRows(kbMaster.tags,'kbSearchTags',['tag_id','name']).map(", 1)

# Default KolayBi navigation opens transaction mode, not the master-data dump.
html = html.replace("show('kolaybi',this);loadKolaybiMaster();kbLoadConnection()", "show('kolaybi',this);kbMainMode('transaction')", 1)
html = html.replace("show('kolaybi',this);loadKolaybiMaster()", "show('kolaybi',this);kbMainMode('transaction')", 1)

# Responsive two-card layout.
css = '<style>@media(max-width:1000px){#kbSingleResult{grid-template-columns:1fr!important}}</style>'
if '</head>' in html and '#kbSingleResult{grid-template-columns' not in html:
    html = html.replace('</head>', css + '</head>', 1)

core.HTML = html
print('[SAMA] KolayBi single-SCNA workspace active: PURCHASE + SALE separated, master rows hidden by default')
