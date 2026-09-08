import os
import time
import requests
from fastapi import HTTPException
import kolaybi_web_module_patch as base

app = base.app
core = base.core
kdb = base.kdb
html = core.HTML

BASE_URL = (os.getenv('KOLAYBI_BASE_URL') or '').rstrip('/')
API_KEY = os.getenv('KOLAYBI_API_KEY') or ''
CHANNEL = os.getenv('KOLAYBI_CHANNEL') or ''
SESSION = requests.Session()
_TOKEN = ''
_TOKEN_TIME = 0.0


def _token():
    global _TOKEN, _TOKEN_TIME
    if _TOKEN and time.time() - _TOKEN_TIME < 23 * 60 * 60:
        return _TOKEN
    if not BASE_URL or not API_KEY or not CHANNEL:
        raise HTTPException(status_code=500, detail='KolayBi bağlantı ayarları eksik: KOLAYBI_BASE_URL / KOLAYBI_API_KEY / KOLAYBI_CHANNEL')
    try:
        r = SESSION.post(
            f'{BASE_URL}/access_token',
            headers={'Channel': CHANNEL, 'Content-Type': 'application/json'},
            json={'api_key': API_KEY}, timeout=30,
        )
        r.raise_for_status()
        _TOKEN = str((r.json() or {}).get('data') or '').strip()
        if not _TOKEN:
            raise RuntimeError('Token boş döndü.')
        _TOKEN_TIME = time.time()
        return _TOKEN
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'KolayBi token alınamadı: {e}')


def _get(path, params=None):
    try:
        r = SESSION.get(
            f'{BASE_URL}/{path.lstrip("/")}',
            headers={'Authorization': f'Bearer {_token()}', 'Channel': CHANNEL},
            params=params or {}, timeout=35,
        )
        r.raise_for_status()
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        body = ''
        try: body = (r.text or '')[:500]
        except Exception: pass
        raise RuntimeError(f'GET /{path}: {e} {body}')


def _rows(resp):
    if isinstance(resp, list):
        return [x for x in resp if isinstance(x, dict)]
    if not isinstance(resp, dict):
        return []
    data = resp.get('data')
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ('data','items','records','results','associates','contacts','products','projects','tags'):
            v = data.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    for key in ('items','records','results','associates','contacts','products','projects','tags'):
        v = resp.get(key)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
    return []


def _txt(v):
    return str(v or '').strip()


def _id(row):
    if not isinstance(row, dict): return ''
    for key in ('id','product_id','project_id','contact_id','associate_id','tag_id'):
        v = _txt(row.get(key))
        if v: return v
    return ''


def _address_id(row):
    if not isinstance(row, dict): return ''
    for key in ('address_id','default_address_id','billing_address_id'):
        v = _txt(row.get(key))
        if v: return v
    for key in ('address','default_address','billing_address'):
        v = row.get(key)
        if isinstance(v, dict):
            got = _id(v)
            if got: return got
    for key in ('addresses','contact_addresses'):
        v = row.get(key)
        if isinstance(v, list) and v:
            for item in v:
                got = _id(item)
                if got: return got
    return ''


def _extract_plate(row):
    hay = ' '.join([
        _txt(row.get('name')), _txt(row.get('title')), _txt(row.get('company_name')),
        _txt(row.get('associate_name')), _txt(row.get('code')), _txt(row.get('surname')),
    ]).upper()
    import re
    m = re.search(r'\b\d{2}[A-Z]\d{4,6}\b', hay.replace(' ', ''))
    return m.group(0) if m else ''


def _fetch_candidates(endpoints, params_list, nested_names):
    errors=[]
    for ep in endpoints:
        for params in params_list:
            try:
                resp=_get(ep,params)
                rows=_rows(resp)
                if rows:
                    return rows, errors
            except Exception as e:
                errors.append(str(e))
    return [], errors


def _sync_associates():
    all_rows=[]; seen=set(); errors=[]; page_size=100
    for page in range(1,51):
        page_rows=[]
        for params in ({'page':page,'per_page':page_size},{'page':page,'limit':page_size}):
            try:
                page_rows=_rows(_get('associates',params))
                if page_rows: break
            except Exception as e:
                errors.append(str(e))
        if not page_rows:
            if page==1:
                try: page_rows=_rows(_get('associates',{}))
                except Exception as e: errors.append(str(e))
            if not page_rows: break
        new=0
        for r in page_rows:
            rid=_id(r)
            name=_txt(r.get('name') or r.get('title') or r.get('company_name') or r.get('associate_name'))
            code=_txt(r.get('code') or r.get('associate_code') or r.get('contact_code'))
            uniq=rid or f'{name}|{code}'
            if uniq in seen: continue
            seen.add(uniq); all_rows.append(r); new+=1
        if new==0 or len(page_rows)<page_size: break
    c=kdb(); count=0
    try:
        for r in all_rows:
            cid=_id(r); name=_txt(r.get('name') or r.get('title') or r.get('company_name') or r.get('associate_name'))
            code=_txt(r.get('code') or r.get('associate_code') or r.get('contact_code'))
            plate=_extract_plate(r)
            key=(code or name or cid).upper()
            if not key or not cid: continue
            c.execute('''INSERT INTO associates(key,name,plate,contact_id,address_id,is_active,note,updated_at)
                         VALUES(?,?,?,?,?,1,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(key) DO UPDATE SET name=excluded.name,plate=CASE WHEN excluded.plate<>'' THEN excluded.plate ELSE associates.plate END,
                         contact_id=excluded.contact_id,address_id=CASE WHEN excluded.address_id<>'' THEN excluded.address_id ELSE associates.address_id END,
                         is_active=1,note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                      (key,name,plate,cid,_address_id(r),'KolayBi API sync'))
            count+=1
        c.commit()
    finally: c.close()
    return count, errors[-5:]


def _sync_products():
    rows, errors=_fetch_candidates(['products'],[{}, {'per_page':100},{'limit':100},{'page':1}],('products',))
    c=kdb(); count=0
    try:
        for r in rows:
            pid=_id(r)
            name=_txt(r.get('name') or r.get('product_name') or r.get('item_name') or r.get('title'))
            code=_txt(r.get('code') or r.get('product_code') or r.get('sku')) or name
            unit=_txt(r.get('unit') or r.get('unit_name') or r.get('unit_code') or r.get('quantity_unit')) or 'ADET'
            if not pid or not code: continue
            api_code=('API_'+pid).upper()
            c.execute('''INSERT INTO products(code,name_tr,name_en,product_id,unit,is_active,note,updated_at)
                         VALUES(?,?,?,?,?,1,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(code) DO UPDATE SET name_tr=excluded.name_tr,name_en=excluded.name_en,
                         product_id=excluded.product_id,unit=excluded.unit,is_active=1,note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                      (api_code,name,name,pid,unit.upper(),'KolayBi API: '+code))
            count+=1
        c.commit()
    finally: c.close()
    return count, errors[-5:]


def _sync_projects():
    rows, errors=_fetch_candidates(['projects','project','project/list','projects/list'],[{}, {'per_page':100},{'limit':100},{'page':1}],('projects',))
    c=kdb(); count=0
    try:
        for r in rows:
            pid=_id(r)
            code=_txt(r.get('code') or r.get('project_code') or r.get('projectCode') or r.get('project_no')) or ('PROJECT_'+pid)
            name=_txt(r.get('name') or r.get('title') or r.get('project_name') or r.get('ad')) or code
            if not pid: continue
            c.execute('''INSERT INTO projects(code,name,project_id,is_active,note,updated_at)
                         VALUES(?,?,?,1,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(code) DO UPDATE SET name=excluded.name,project_id=excluded.project_id,is_active=1,note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                      (code.upper(),name,pid,'KolayBi API sync'))
            count+=1
        c.commit()
    finally: c.close()
    return count, errors[-5:]


def _sync_tags():
    rows, errors=_fetch_candidates(['tags','tag','tags/list','tag/list'],[{}, {'type':'CommercialDoc'},{'taggable_type':'CommercialDoc'},{'model':'CommercialDoc'},{'per_page':100},{'limit':100}],('tags',))
    c=kdb(); count=0
    try:
        for r in rows:
            tid=_id(r)
            name=_txt(r.get('name') or r.get('title') or r.get('label') or r.get('tag_name'))
            if not tid or not name: continue
            c.execute('''INSERT INTO tags(tag_id,name,is_default,is_active,note,updated_at)
                         VALUES(?,?,COALESCE((SELECT is_default FROM tags WHERE tag_id=?),0),1,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(tag_id) DO UPDATE SET name=excluded.name,is_active=1,note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                      (tid,name,tid,'KolayBi API sync'))
            count+=1
        c.commit()
    finally: c.close()
    return count, errors[-5:]


# Upgrade existing master DB with tags + sync state.
c=kdb()
try:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS tags(
      tag_id TEXT PRIMARY KEY,
      name TEXT DEFAULT '',
      is_default INTEGER DEFAULT 0,
      is_active INTEGER DEFAULT 1,
      note TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sync_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT,
      row_count INTEGER DEFAULT 0,
      ok INTEGER DEFAULT 0,
      detail TEXT DEFAULT '',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    c.execute("INSERT OR IGNORE INTO tags(tag_id,name,is_default,is_active,note) VALUES('297063','FREIGHT',1,1,'Bilinen sabit etiket')")
    c.execute("INSERT OR IGNORE INTO tags(tag_id,name,is_default,is_active,note) VALUES('319791','OTOMATIK',1,1,'Bilinen sabit etiket')")
    c.commit()
finally: c.close()


@app.get('/api/kolaybi/connection')
def kb_connection():
    return {'configured':bool(BASE_URL and API_KEY and CHANNEL),'base_url':BASE_URL,'channel':CHANNEL,'api_key_set':bool(API_KEY)}


@app.post('/api/kolaybi/sync/{kind}')
def kb_sync(kind:str):
    base._admin_required()
    fn={'associates':_sync_associates,'products':_sync_products,'projects':_sync_projects,'tags':_sync_tags}.get(kind)
    if not fn: raise HTTPException(status_code=400,detail='Geçersiz senkronizasyon türü.')
    try:
        count, errors=fn(); ok=True; detail=' | '.join(errors)
    except HTTPException: raise
    except Exception as e:
        count=0; ok=False; detail=str(e)
    c=kdb()
    try:
        c.execute('INSERT INTO sync_log(kind,row_count,ok,detail) VALUES(?,?,?,?)',(kind,count,1 if ok else 0,detail[:1200])); c.commit()
    finally: c.close()
    if not ok: raise HTTPException(status_code=502,detail=detail)
    return {'ok':True,'kind':kind,'count':count,'warnings':errors}


@app.post('/api/kolaybi/sync-all')
def kb_sync_all():
    base._admin_required()
    out={}
    for kind,fn in [('associates',_sync_associates),('products',_sync_products),('projects',_sync_projects),('tags',_sync_tags)]:
        try:
            count, errors=fn(); out[kind]={'ok':True,'count':count,'warnings':errors}
        except Exception as e:
            out[kind]={'ok':False,'count':0,'error':str(e)}
    return {'ok':all(x.get('ok') for x in out.values()),'results':out}


@app.post('/api/kolaybi/master/tag/{tag_id}/default')
def kb_tag_default(tag_id:str, enabled:bool=True):
    base._admin_required()
    c=kdb()
    try:
        c.execute('UPDATE tags SET is_default=?,updated_at=CURRENT_TIMESTAMP WHERE tag_id=?',(1 if enabled else 0,str(tag_id))); c.commit()
        return {'ok':True}
    finally:c.close()


# Extend master response with tags and latest syncs by replacing the route handler safely.
def _master_v2():
    c=kdb()
    try:
        return {
          'products':[dict(r) for r in c.execute('SELECT * FROM products ORDER BY is_active DESC,code').fetchall()],
          'associates':[dict(r) for r in c.execute('SELECT * FROM associates ORDER BY is_active DESC,name,key').fetchall()],
          'projects':[dict(r) for r in c.execute('SELECT * FROM projects ORDER BY is_active DESC,code').fetchall()],
          'tags':[dict(r) for r in c.execute('SELECT * FROM tags ORDER BY is_default DESC,name').fetchall()],
          'sync_log':[dict(r) for r in c.execute('SELECT * FROM sync_log ORDER BY id DESC LIMIT 20').fetchall()],
        }
    finally:c.close()
for route in app.routes:
    if getattr(route,'path',None)=='/api/kolaybi/master' and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint=_master_v2
        if getattr(route,'dependant',None) is not None: route.dependant.call=_master_v2
        break

# UI: add one-click sync controls and Tags pane. Stay inside existing HTML/JS block.
syncbar='''<div class="kb-syncbar"><button class="btn primary" onclick="kbSyncAll()">KOLAYBI'DEN TÜMÜNÜ ÇEK</button><button class="btn secondary" onclick="kbSync('associates')">CARİLERİ ÇEK</button><button class="btn secondary" onclick="kbSync('products')">ÜRÜNLERİ ÇEK</button><button class="btn secondary" onclick="kbSync('projects')">PROJELERİ ÇEK</button><button class="btn secondary" onclick="kbSync('tags')">ETİKETLERİ ÇEK</button><span id="kbSyncState" class="section-note"></span></div>'''
anchor='<div class="kolaybi-previewbar">'
if anchor in html and 'kbSyncAll()' not in html:
    html=html.replace(anchor,syncbar+'\n  '+anchor,1)

old_tabs='<button class="btn secondary" onclick="kbTab(\'projects\')">PROJELER / PROJECTS</button>'
new_tabs=old_tabs+'\n    <button class="btn secondary" onclick="kbTab(\'tags\')">ETİKETLER / TAGS</button>'
html=html.replace(old_tabs,new_tabs,1)

tags_pane='''<div id="kbTags" class="kb-pane" style="display:none"><div class="table"><table><thead><tr><th>ETİKET</th><th>TAG ID</th><th>VARSAYILAN</th></tr></thead><tbody id="kbTagRows"></tbody></table></div></div>'''
projects_close='</div>\n</section>'
pos=html.find(projects_close, html.find('id="kbProjects"'))
if pos!=-1 and 'id="kbTags"' not in html:
    html=html[:pos+6]+'\n  '+tags_pane+html[pos+6:]

css='.kb-syncbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:10px 0 14px;padding:10px;border:1px solid var(--line);border-radius:12px}.kb-syncbar .btn{min-height:38px}'
if '</style>' in html and '.kb-syncbar{' not in html:
    html=html.replace('</style>',css+'</style>',1)

html=html.replace("let kbMaster={products:[],associates:[],projects:[]};","let kbMaster={products:[],associates:[],projects:[],tags:[],sync_log:[]};",1)
html=html.replace("['Products','Associates','Projects']","['Products','Associates','Projects','Tags']",1)
render_anchor="  const ar=document.getElementById('kbAssociateRows');"
render_add="  const tr=document.getElementById('kbTagRows');if(tr)tr.innerHTML=(kbMaster.tags||[]).map(x=>`<tr><td>${kbEsc(x.name)}</td><td>${kbEsc(x.tag_id)}</td><td><label><input type=\"checkbox\" ${Number(x.is_default)?'checked':''} onchange=\"kbTagDefault('${kbEsc(x.tag_id)}',this.checked)\"> Varsayılan</label></td></tr>`).join('');\n"
if render_anchor in html and "getElementById('kbTagRows')" not in html:
    html=html.replace(render_anchor,render_add+render_anchor,1)

helper="""
async function kbSync(kind){const s=document.getElementById('kbSyncState');if(s)s.textContent='ÇEKİLİYOR...';try{const r=await api('/api/kolaybi/sync/'+kind,{method:'POST'});if(s)s.textContent=(r.count||0)+' kayıt alındı';await loadKolaybiMaster();}catch(e){if(s)s.textContent='HATA: '+(e.message||e);}}
async function kbSyncAll(){const s=document.getElementById('kbSyncState');if(s)s.textContent='TÜM LİSTELER ÇEKİLİYOR...';try{const r=await api('/api/kolaybi/sync-all',{method:'POST'});const z=r.results||{};if(s)s.textContent='Cari '+(z.associates?.count||0)+' | Ürün '+(z.products?.count||0)+' | Proje '+(z.projects?.count||0)+' | Etiket '+(z.tags?.count||0);await loadKolaybiMaster();}catch(e){if(s)s.textContent='HATA: '+(e.message||e);}}
async function kbTagDefault(id,on){try{await api('/api/kolaybi/master/tag/'+encodeURIComponent(id)+'/default?enabled='+(on?'true':'false'),{method:'POST'});await loadKolaybiMaster();}catch(e){alert(e.message||e);}}
"""
marker='async function loadKolaybiMaster(){'
if marker in html and 'async function kbSyncAll()' not in html:
    html=html.replace(marker,helper+'\n'+marker,1)

core.HTML=html
print(f'[SAMA] KolayBi API sync active: configured={bool(BASE_URL and API_KEY and CHANNEL)}, tags=1, sync_all=1')
