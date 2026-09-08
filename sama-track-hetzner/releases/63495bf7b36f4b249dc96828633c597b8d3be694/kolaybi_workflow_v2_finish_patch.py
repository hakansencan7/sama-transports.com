from fastapi import Request, HTTPException
import kolaybi_workflow_v2_patch as base

app = base.app
core = base.core
kdb = base.kdb
sync = base.sync
html = core.HTML

# Preserve old web purchase-send history in the new PURCHASE/SALE separated ledger.
c = kdb()
try:
    old_exists = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sent_documents'").fetchone()
    if old_exists:
        c.execute('''INSERT OR IGNORE INTO sent_documents_v2(scna,doc_kind,document_id,endpoint,payload_json,response_json,tags_json,sent_at)
                     SELECT scna,'PURCHASE',document_id,endpoint,payload_json,response_json,tags_json,sent_at
                     FROM sent_documents''')
    c.commit()
finally:
    c.close()


async def _sale_alias_save_safe(request: Request):
    sync.base._admin_required()
    b = await request.json()
    alias = base._txt(b.get('alias'))
    pid = base._txt(b.get('product_id'))
    pname = base._txt(b.get('product_name'))
    unit = base._txt(b.get('unit') or 'KG').upper()
    note = base._txt(b.get('note'))
    if not alias:
        raise HTTPException(status_code=400, detail='Alias / bölge adı boş olamaz.')
    if not pid or not pid.isdigit():
        raise HTTPException(status_code=400, detail='Product ID sayısal ve dolu olmalı.')
    c = kdb()
    try:
        # Normalized alias is the real key, just like the old working alias cache.
        c.execute('DELETE FROM sale_product_aliases WHERE alias_key=?', (base._norm(alias),))
        c.execute('''INSERT INTO sale_product_aliases(alias,alias_key,product_id,product_name,unit,note,updated_at)
                     VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                  (alias,base._norm(alias),pid,pname,unit,note))
        c.commit()
    finally:
        c.close()
    return {'ok': True}


# Replace the first registered alias-save route so punctuation/spacing variants update safely.
for route in app.routes:
    if getattr(route,'path',None) == '/api/kolaybi/sale-alias' and 'POST' in (getattr(route,'methods',set()) or set()):
        route.endpoint = _sale_alias_save_safe
        if getattr(route,'dependant',None) is not None:
            route.dependant.call = _sale_alias_save_safe
        break

# Every settings tab must hide the SALE alias pane when another tab is selected.
for name in ('products','associates','projects','tags'):
    html = html.replace(f"onclick=\"kbTab('{name}')\"", f"onclick=\"kbTabV2('{name}')\"")

# Put the one-time/refresh sync next to the transaction search, not buried among 2000 master rows.
needle = '<button class="btn primary" onclick="kbLoadSingleV2()">SCNA KONTROLÜNÜ GETİR</button>'
if needle in html and 'kbSyncReferenceV2()' not in html:
    html = html.replace(needle, needle + '<button class="btn secondary" onclick="kbSyncReferenceV2()">CARİ / ÜRÜN VERİSİNİ YENİLE</button>', 1)

helper = r'''
async function kbSyncReferenceV2(){
  const s=document.getElementById('kbSingleState');if(s)s.textContent='KOLAYBI CARİ / ÜRÜN / PROJE / ETİKET VERİSİ YENİLENİYOR...';
  try{
    const r=await api('/api/kolaybi/sync-all',{method:'POST'});const z=r.results||{};
    if(s)s.innerHTML='<span class="kb-ready">✓ YENİLENDİ | Cari '+(z.associates?.count||0)+' | Ürün '+(z.products?.count||0)+' | Proje '+(z.projects?.count||0)+' | Etiket '+(z.tags?.count||0)+'</span>';
    try{await loadKolaybiMaster();}catch(e){}
    const scna=String(document.getElementById('kbSingleScna')?.value||'').trim();if(scna)await kbLoadSingleV2();
  }catch(e){if(s)s.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
'''
marker = 'async function kbLoadSingleV2(){'
if marker in html and 'async function kbSyncReferenceV2' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

core.HTML = html
print('[SAMA] KolayBi workflow V2 finish active: history migrated, alias normalized, transaction refresh exposed')
