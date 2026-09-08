import sqlite3
from pathlib import Path
from fastapi import Request, HTTPException
import entry_other_and_print_items_patch as base

app = base.app
core = base.core
html = core.HTML

KOLAYBI_DB = Path(core.VOLUME_DIR) / 'kolaybi_master.db'


def kdb():
    c = sqlite3.connect(KOLAYBI_DB)
    c.row_factory = sqlite3.Row
    return c


def init_kolaybi_master():
    c = kdb()
    try:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS products(
          code TEXT PRIMARY KEY COLLATE NOCASE,
          name_tr TEXT DEFAULT '',
          name_en TEXT DEFAULT '',
          product_id TEXT DEFAULT '',
          unit TEXT DEFAULT 'ADET',
          is_active INTEGER DEFAULT 1,
          note TEXT DEFAULT '',
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS associates(
          key TEXT PRIMARY KEY COLLATE NOCASE,
          name TEXT DEFAULT '',
          plate TEXT DEFAULT '',
          contact_id TEXT DEFAULT '',
          address_id TEXT DEFAULT '',
          is_active INTEGER DEFAULT 1,
          note TEXT DEFAULT '',
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS projects(
          code TEXT PRIMARY KEY COLLATE NOCASE,
          name TEXT DEFAULT '',
          project_id TEXT DEFAULT '',
          is_active INTEGER DEFAULT 1,
          note TEXT DEFAULT '',
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        for row in [
            ('WEIGHBRIDGE','KANTAR','WEIGHBRIDGE','ADET'),
            ('PARKING','PARK','PARKING','GUN'),
            ('WAITING','BEKLEME','WAITING','GUN'),
            ('OTHER','DİĞER','OTHER','ADET'),
            ('ROAD_FUEL','YOLDA MAZOT','ROAD FUEL','LT'),
        ]:
            c.execute('''INSERT OR IGNORE INTO products(code,name_tr,name_en,unit,is_active)
                         VALUES(?,?,?,?,1)''', row)
        c.execute('''INSERT OR IGNORE INTO projects(code,name,project_id,is_active)
                     VALUES('FREIGHT','FREIGHT','84937',1)''')
        c.commit()
    finally:
        c.close()


init_kolaybi_master()


def _admin_required():
    user = core.CURRENT_AUTH_USER.get() or {}
    if str(user.get('role') or '').upper() != 'ADMIN':
        raise HTTPException(status_code=403, detail='KolayBi eşleştirme ayarlarını sadece ADMIN değiştirebilir.')


def _digits_or_blank(value, label):
    v = str(value or '').strip()
    if v and not v.isdigit():
        raise HTTPException(status_code=400, detail=f'{label} sayısal olmalı.')
    return v


@app.get('/api/kolaybi/master')
def kolaybi_master_list():
    c = kdb()
    try:
        return {
            'products':[dict(r) for r in c.execute('SELECT * FROM products ORDER BY is_active DESC,code').fetchall()],
            'associates':[dict(r) for r in c.execute('SELECT * FROM associates ORDER BY is_active DESC,name,key').fetchall()],
            'projects':[dict(r) for r in c.execute('SELECT * FROM projects ORDER BY is_active DESC,code').fetchall()],
        }
    finally:
        c.close()


@app.post('/api/kolaybi/master/product')
async def kolaybi_master_product(request: Request):
    _admin_required()
    b = await request.json()
    code = str(b.get('code') or '').strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail='Ürün kodu boş olamaz.')
    pid = _digits_or_blank(b.get('product_id'), 'Product ID')
    c = kdb()
    try:
        c.execute('''INSERT INTO products(code,name_tr,name_en,product_id,unit,is_active,note,updated_at)
                     VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(code) DO UPDATE SET name_tr=excluded.name_tr,name_en=excluded.name_en,
                     product_id=excluded.product_id,unit=excluded.unit,is_active=excluded.is_active,
                     note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                  (code,str(b.get('name_tr') or '').strip(),str(b.get('name_en') or '').strip(),pid,
                   str(b.get('unit') or 'ADET').strip().upper(),1 if b.get('is_active',True) else 0,
                   str(b.get('note') or '').strip()))
        c.commit()
        return {'ok':True}
    finally:
        c.close()


@app.post('/api/kolaybi/master/associate')
async def kolaybi_master_associate(request: Request):
    _admin_required()
    b = await request.json()
    name = str(b.get('name') or '').strip()
    plate = str(b.get('plate') or '').strip().upper()
    key = str(b.get('key') or '').strip().upper() or name.upper() or plate
    if not key:
        raise HTTPException(status_code=400, detail='Cari anahtarı, adı veya plakası gerekli.')
    contact_id = _digits_or_blank(b.get('contact_id'), 'Contact ID')
    address_id = _digits_or_blank(b.get('address_id'), 'Address ID')
    c = kdb()
    try:
        c.execute('''INSERT INTO associates(key,name,plate,contact_id,address_id,is_active,note,updated_at)
                     VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(key) DO UPDATE SET name=excluded.name,plate=excluded.plate,
                     contact_id=excluded.contact_id,address_id=excluded.address_id,is_active=excluded.is_active,
                     note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                  (key,name,plate,contact_id,address_id,1 if b.get('is_active',True) else 0,str(b.get('note') or '').strip()))
        c.commit()
        return {'ok':True}
    finally:
        c.close()


@app.post('/api/kolaybi/master/project')
async def kolaybi_master_project(request: Request):
    _admin_required()
    b = await request.json()
    code = str(b.get('code') or '').strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail='Proje kodu boş olamaz.')
    project_id = _digits_or_blank(b.get('project_id'), 'Project ID')
    c = kdb()
    try:
        c.execute('''INSERT INTO projects(code,name,project_id,is_active,note,updated_at)
                     VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(code) DO UPDATE SET name=excluded.name,project_id=excluded.project_id,
                     is_active=excluded.is_active,note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                  (code,str(b.get('name') or '').strip(),project_id,1 if b.get('is_active',True) else 0,
                   str(b.get('note') or '').strip()))
        c.commit()
        return {'ok':True}
    finally:
        c.close()


@app.delete('/api/kolaybi/master/{kind}/{key}')
def kolaybi_master_delete(kind: str, key: str):
    _admin_required()
    table = {'product':'products','associate':'associates','project':'projects'}.get(kind)
    pk = {'product':'code','associate':'key','project':'code'}.get(kind)
    if not table:
        raise HTTPException(status_code=400, detail='Geçersiz kayıt türü.')
    c = kdb()
    try:
        c.execute(f'DELETE FROM {table} WHERE UPPER({pk})=UPPER(?)',(str(key).strip(),))
        c.commit()
        return {'ok':True}
    finally:
        c.close()


@app.get('/api/kolaybi/preview/{scna}')
def kolaybi_preview(scna: str):
    key = str(scna or '').strip()
    c = core.db()
    try:
        trip = c.execute('''SELECT t.*, COALESCE(cu.name,'') customer_name
                            FROM trips t LEFT JOIN customers cu ON cu.id=t.customer_id
                            WHERE UPPER(TRIM(t.scna))=UPPER(TRIM(?))''',(key,)).fetchone()
        if not trip:
            raise HTTPException(status_code=404, detail='SCNA bulunamadı.')
        fixed = c.execute('''SELECT code,qty,unit_price,total FROM trip_entry_fixed_expenses
                             WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) ORDER BY slot''',(key,)).fetchall()
        fuels = c.execute('''SELECT liters,total,note FROM fuel_purchases
                             WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) ORDER BY id''',(key,)).fetchall()
    finally:
        c.close()
    kc = kdb()
    try:
        products = {str(r['code']).upper():dict(r) for r in kc.execute('SELECT * FROM products WHERE is_active=1').fetchall()}
        plate = str(trip['plate'] or '').strip().upper()
        assoc = kc.execute('''SELECT * FROM associates WHERE is_active=1 AND UPPER(TRIM(plate))=UPPER(TRIM(?))
                              ORDER BY updated_at DESC LIMIT 1''',(plate,)).fetchone()
        if not assoc and str(trip['customer_name'] or '').strip():
            assoc = kc.execute('''SELECT * FROM associates WHERE is_active=1 AND UPPER(TRIM(name))=UPPER(TRIM(?))
                                  ORDER BY updated_at DESC LIMIT 1''',(str(trip['customer_name']).strip(),)).fetchone()
        project = kc.execute("SELECT * FROM projects WHERE is_active=1 AND UPPER(code)='FREIGHT' LIMIT 1").fetchone()
    finally:
        kc.close()
    items=[]
    for r in fixed:
        if float(r['total'] or 0)<=0: continue
        code=str(r['code'] or '').upper(); p=products.get(code) or {}
        items.append({'code':code,'name':(p.get('name_tr') or code)+' / '+(p.get('name_en') or code),
                      'product_id':p.get('product_id',''),'quantity':float(r['qty'] or 0),
                      'unit_price':float(r['unit_price'] or 0),'total':float(r['total'] or 0),'description':''})
    for slot in (1,2):
        amount=float(trip[f'entry_other_expense_{slot}'] or 0)
        note=str(trip[f'entry_other_note_{slot}'] or '').strip()
        if amount or note:
            p=products.get('OTHER') or {}
            items.append({'code':'OTHER','name':(p.get('name_tr') or 'DİĞER')+' / '+(p.get('name_en') or 'OTHER'),
                          'product_id':p.get('product_id',''),'quantity':1,'unit_price':amount,'total':amount,'description':note})
    road_total=sum(float(r['total'] or 0) for r in fuels)
    road_liters=sum(float(r['liters'] or 0) for r in fuels)
    if road_total:
        p=products.get('ROAD_FUEL') or {}
        items.append({'code':'ROAD_FUEL','name':(p.get('name_tr') or 'YOLDA MAZOT')+' / '+(p.get('name_en') or 'ROAD FUEL'),
                      'product_id':p.get('product_id',''),'quantity':road_liters or 1,
                      'unit_price':(road_total/road_liters if road_liters else road_total),'total':road_total,
                      'description':'; '.join([str(r['note'] or '').strip() for r in fuels if str(r['note'] or '').strip()])})
    missing=[x['code'] for x in items if not str(x.get('product_id') or '').strip()]
    return {'ok':True,'scna':key,'plate':str(trip['plate'] or ''),'customer':str(trip['customer_name'] or ''),
            'contact':dict(assoc) if assoc else None,'project':dict(project) if project else None,'items':items,
            'missing_product_codes':sorted(set(missing)),
            'ready':bool(items) and not missing and bool(assoc and str(assoc['contact_id'] or '').strip()) and bool(project and str(project['project_id'] or '').strip())}


# Main navigation entry. No separate script tag: helpers are inserted into the existing app JS.
nav_anchor = '<div class="nav-group">\n  <button class="nav-group-title" onclick="toggleNavGroup(this)">SEVKİYAT <span>▸</span></button>'
nav_block = '''<div class="nav-group">
  <button class="nav-group-title" onclick="toggleNavGroup(this)">KOLAYBI <span>▸</span></button>
  <div class="nav-group-items">
    <button onclick="show('kolaybi',this);loadKolaybiMaster()">KolayBi Panel</button>
  </div>
</div>

'''
nav_inserted=0
if nav_anchor in html and "show('kolaybi'" not in html:
    html=html.replace(nav_anchor,nav_block+nav_anchor,1); nav_inserted=1

panel = r'''
<section id="kolaybi" class="panel">
  <div class="filterbar"><b>KOLAYBI PANEL</b><span class="section-note">Ürün / Cari / Proje ID Eşleştirme</span></div>
  <div class="kolaybi-previewbar">
    <input id="kbScna" placeholder="SCNA yaz...">
    <button class="btn primary" onclick="kbPreview()">SCNA ÖNİZLE</button>
    <span id="kbPreviewState" class="section-note"></span>
  </div>
  <div id="kbPreviewBox" class="calc" style="display:none;margin-bottom:14px"></div>
  <div class="kb-tabs">
    <button class="btn secondary" onclick="kbTab('products')">ÜRÜNLER / PRODUCTS</button>
    <button class="btn secondary" onclick="kbTab('associates')">CARİLER / CONTACTS</button>
    <button class="btn secondary" onclick="kbTab('projects')">PROJELER / PROJECTS</button>
  </div>
  <div id="kbProducts" class="kb-pane">
    <div class="grid">
      <div class="field"><label>KOD / CODE</label><input id="kbPCode" placeholder="WEIGHBRIDGE"></div>
      <div class="field"><label>TÜRKÇE AD</label><input id="kbPTr" placeholder="KANTAR"></div>
      <div class="field"><label>ENGLISH NAME</label><input id="kbPEn" placeholder="WEIGHBRIDGE"></div>
      <div class="field"><label>PRODUCT ID</label><input id="kbPId" inputmode="numeric"></div>
      <div class="field"><label>BİRİM / UNIT</label><select id="kbPUnit"><option>ADET</option><option>GUN</option><option>LT</option><option>KG</option></select></div>
      <div class="field"><label>NOT / NOTE</label><input id="kbPNote"></div>
    </div>
    <button class="btn primary" onclick="kbSaveProduct()">ÜRÜN KAYDET / SAVE PRODUCT</button>
    <div class="table" style="margin-top:12px"><table><thead><tr><th>KOD</th><th>TR</th><th>EN</th><th>PRODUCT ID</th><th>BİRİM</th><th>İŞLEM</th></tr></thead><tbody id="kbProductRows"></tbody></table></div>
  </div>
  <div id="kbAssociates" class="kb-pane" style="display:none">
    <div class="grid">
      <div class="field"><label>CARİ ANAHTAR / KEY</label><input id="kbAKey"></div>
      <div class="field"><label>CARİ ADI / CONTACT NAME</label><input id="kbAName"></div>
      <div class="field"><label>PLAKA / PLATE</label><input id="kbAPlate"></div>
      <div class="field"><label>CONTACT ID</label><input id="kbAContact" inputmode="numeric"></div>
      <div class="field"><label>ADDRESS ID</label><input id="kbAAddress" inputmode="numeric"></div>
      <div class="field"><label>NOT / NOTE</label><input id="kbANote"></div>
    </div>
    <button class="btn primary" onclick="kbSaveAssociate()">CARİ KAYDET / SAVE CONTACT</button>
    <div class="table" style="margin-top:12px"><table><thead><tr><th>ANAHTAR</th><th>CARİ</th><th>PLAKA</th><th>CONTACT ID</th><th>ADDRESS ID</th><th>İŞLEM</th></tr></thead><tbody id="kbAssociateRows"></tbody></table></div>
  </div>
  <div id="kbProjects" class="kb-pane" style="display:none">
    <div class="grid">
      <div class="field"><label>PROJE KODU / CODE</label><input id="kbPrCode" value="FREIGHT"></div>
      <div class="field"><label>PROJE ADI / NAME</label><input id="kbPrName" value="FREIGHT"></div>
      <div class="field"><label>PROJECT ID</label><input id="kbPrId" inputmode="numeric" value="84937"></div>
      <div class="field"><label>NOT / NOTE</label><input id="kbPrNote"></div>
    </div>
    <button class="btn primary" onclick="kbSaveProject()">PROJE KAYDET / SAVE PROJECT</button>
    <div class="table" style="margin-top:12px"><table><thead><tr><th>KOD</th><th>PROJE</th><th>PROJECT ID</th><th>İŞLEM</th></tr></thead><tbody id="kbProjectRows"></tbody></table></div>
  </div>
</section>

'''
panel_anchor='<section id="dash" class="panel active">'
panel_inserted=0
if panel_anchor in html and 'id="kolaybi"' not in html:
    html=html.replace(panel_anchor,panel+panel_anchor,1); panel_inserted=1

css=r'''
.kolaybi-previewbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}.kolaybi-previewbar input{min-width:220px}.kb-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 14px}.kb-pane{border:1px solid var(--line);border-radius:14px;padding:13px}.kb-ready{color:#15803d;font-weight:900}.kb-missing{color:#b91c1c;font-weight:900}.kb-item{display:grid;grid-template-columns:1fr auto;gap:8px;padding:7px 0;border-bottom:1px solid var(--line)}
'''
if '</style>' in html and '.kb-tabs{' not in html:
    html=html.replace('</style>',css+'</style>',1)

helper=r'''
let kbMaster={products:[],associates:[],projects:[]};
function kbEsc(v){return typeof esc==='function'?esc(v):String(v??'').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));}
function kbTab(name){['Products','Associates','Projects'].forEach(x=>{const e=document.getElementById('kb'+x);if(e)e.style.display=(x.toLowerCase()===name?'':'none');});}
async function loadKolaybiMaster(){
  try{kbMaster=await api('/api/kolaybi/master');kbRenderMaster();}catch(e){console.error(e);}
}
function kbRenderMaster(){
  const pr=document.getElementById('kbProductRows');if(pr)pr.innerHTML=(kbMaster.products||[]).map(x=>`<tr><td>${kbEsc(x.code)}</td><td>${kbEsc(x.name_tr)}</td><td>${kbEsc(x.name_en)}</td><td>${kbEsc(x.product_id||'')}</td><td>${kbEsc(x.unit)}</td><td><button class="btn secondary" onclick="kbEditProduct('${kbEsc(x.code)}')">DÜZENLE</button> <button class="btn danger" onclick="kbDelete('product','${kbEsc(x.code)}')">SİL</button></td></tr>`).join('');
  const ar=document.getElementById('kbAssociateRows');if(ar)ar.innerHTML=(kbMaster.associates||[]).map(x=>`<tr><td>${kbEsc(x.key)}</td><td>${kbEsc(x.name)}</td><td>${kbEsc(x.plate)}</td><td>${kbEsc(x.contact_id||'')}</td><td>${kbEsc(x.address_id||'')}</td><td><button class="btn secondary" onclick="kbEditAssociate('${kbEsc(x.key)}')">DÜZENLE</button> <button class="btn danger" onclick="kbDelete('associate','${kbEsc(x.key)}')">SİL</button></td></tr>`).join('');
  const rr=document.getElementById('kbProjectRows');if(rr)rr.innerHTML=(kbMaster.projects||[]).map(x=>`<tr><td>${kbEsc(x.code)}</td><td>${kbEsc(x.name)}</td><td>${kbEsc(x.project_id||'')}</td><td><button class="btn secondary" onclick="kbEditProject('${kbEsc(x.code)}')">DÜZENLE</button> <button class="btn danger" onclick="kbDelete('project','${kbEsc(x.code)}')">SİL</button></td></tr>`).join('');
}
async function kbPost(url,body){await api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});await loadKolaybiMaster();}
async function kbSaveProduct(){try{await kbPost('/api/kolaybi/master/product',{code:kbPCode.value,name_tr:kbPTr.value,name_en:kbPEn.value,product_id:kbPId.value,unit:kbPUnit.value,note:kbPNote.value,is_active:true});alert('Ürün kaydedildi.');}catch(e){alert(e.message||e);}}
async function kbSaveAssociate(){try{await kbPost('/api/kolaybi/master/associate',{key:kbAKey.value,name:kbAName.value,plate:kbAPlate.value,contact_id:kbAContact.value,address_id:kbAAddress.value,note:kbANote.value,is_active:true});alert('Cari kaydedildi.');}catch(e){alert(e.message||e);}}
async function kbSaveProject(){try{await kbPost('/api/kolaybi/master/project',{code:kbPrCode.value,name:kbPrName.value,project_id:kbPrId.value,note:kbPrNote.value,is_active:true});alert('Proje kaydedildi.');}catch(e){alert(e.message||e);}}
function kbEditProduct(code){const x=(kbMaster.products||[]).find(a=>a.code===code);if(!x)return;kbPCode.value=x.code;kbPTr.value=x.name_tr||'';kbPEn.value=x.name_en||'';kbPId.value=x.product_id||'';kbPUnit.value=x.unit||'ADET';kbPNote.value=x.note||'';window.scrollTo({top:0,behavior:'smooth'});}
function kbEditAssociate(key){const x=(kbMaster.associates||[]).find(a=>a.key===key);if(!x)return;kbAKey.value=x.key;kbAName.value=x.name||'';kbAPlate.value=x.plate||'';kbAContact.value=x.contact_id||'';kbAAddress.value=x.address_id||'';kbANote.value=x.note||'';}
function kbEditProject(code){const x=(kbMaster.projects||[]).find(a=>a.code===code);if(!x)return;kbPrCode.value=x.code;kbPrName.value=x.name||'';kbPrId.value=x.project_id||'';kbPrNote.value=x.note||'';}
async function kbDelete(kind,key){if(!confirm(key+' kaydı silinsin mi?'))return;try{await api('/api/kolaybi/master/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key),{method:'DELETE'});await loadKolaybiMaster();}catch(e){alert(e.message||e);}}
async function kbPreview(){const s=String(kbScna.value||'').trim();if(!s)return;const box=document.getElementById('kbPreviewBox'),state=document.getElementById('kbPreviewState');try{const x=await api('/api/kolaybi/preview/'+encodeURIComponent(s));state.innerHTML=x.ready?'<span class="kb-ready">✓ GÖNDERİME HAZIR</span>':'<span class="kb-missing">EKSİK EŞLEŞTİRME VAR</span>';box.style.display='block';box.innerHTML=`<b>SCNA ${kbEsc(x.scna)} | ${kbEsc(x.plate)}</b><div style="margin:6px 0">Cari: ${kbEsc(x.contact?.name||x.customer||'-')} | Contact ID: ${kbEsc(x.contact?.contact_id||'-')} | Address ID: ${kbEsc(x.contact?.address_id||'-')} | Project ID: ${kbEsc(x.project?.project_id||'-')}</div>`+(x.missing_product_codes?.length?`<div class="kb-missing">Eksik Product ID: ${kbEsc(x.missing_product_codes.join(', '))}</div>`:'')+(x.items||[]).map(i=>`<div class="kb-item"><span><b>${kbEsc(i.name)}</b>${i.description?'<br><small>'+kbEsc(i.description)+'</small>':''}</span><span>${kbEsc(i.quantity)} × ${Number(i.unit_price||0).toLocaleString('tr-TR')} = <b>${Number(i.total||0).toLocaleString('tr-TR')}</b></span></div>`).join('');}catch(e){state.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}}
'''
marker='async function openEntry(scna){'
js_inserted=0
if marker in html and 'function kbSaveProduct' not in html:
    html=html.replace(marker,helper+'\n'+marker,1);js_inserted=1

core.HTML=html
print(f'[SAMA] KolayBi web master module active: nav={nav_inserted}, panel={panel_inserted}, js={js_inserted}, db={KOLAYBI_DB}')
