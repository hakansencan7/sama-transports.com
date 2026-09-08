import kolaybi_connection_settings_patch as base

app = base.app
core = base.core
html = core.HTML

# Add one search box per KolayBi master-data pane. Keep everything inside the
# existing application HTML/JS; no extra <script> tag is introduced.
replacements = [
    (
        '<div id="kbProducts" class="kb-pane">',
        '<div id="kbProducts" class="kb-pane">\n    <div class="filterbar"><input id="kbProductSearch" class="grow" placeholder="Ürün ara: ad / kod / product ID..." oninput="kbRenderMaster()"><span id="kbProductCount" class="section-note"></span></div>',
    ),
    (
        '<div id="kbAssociates" class="kb-pane" style="display:none">',
        '<div id="kbAssociates" class="kb-pane" style="display:none">\n    <div class="filterbar"><input id="kbAssociateSearch" class="grow" placeholder="Cari ara: ad / plaka / contact ID / address ID..." oninput="kbRenderMaster()"><span id="kbAssociateCount" class="section-note"></span></div>',
    ),
    (
        '<div id="kbProjects" class="kb-pane" style="display:none">',
        '<div id="kbProjects" class="kb-pane" style="display:none">\n    <div class="filterbar"><input id="kbProjectSearch" class="grow" placeholder="Proje ara: ad / kod / project ID..." oninput="kbRenderMaster()"><span id="kbProjectCount" class="section-note"></span></div>',
    ),
    (
        '<div id="kbTags" class="kb-pane" style="display:none">',
        '<div id="kbTags" class="kb-pane" style="display:none">\n    <div class="filterbar"><input id="kbTagSearch" class="grow" placeholder="Etiket ara: ad / tag ID..." oninput="kbRenderMaster()"><span id="kbTagCount" class="section-note"></span></div>',
    ),
]
inserted = 0
for old, new in replacements:
    if old in html and new not in html:
        html = html.replace(old, new, 1)
        inserted += 1

helper = r'''
function kbNorm(v){return String(v??'').toLocaleUpperCase('tr-TR').trim();}
function kbMatch(obj,q,fields){if(!q)return true;const needle=kbNorm(q);return fields.some(k=>kbNorm(obj?.[k]).includes(needle));}
function kbFiltered(kind){
  if(kind==='products'){
    const q=document.getElementById('kbProductSearch')?.value||'';
    return (kbMaster.products||[]).filter(x=>kbMatch(x,q,['code','name_tr','name_en','product_id','unit','note']));
  }
  if(kind==='associates'){
    const q=document.getElementById('kbAssociateSearch')?.value||'';
    return (kbMaster.associates||[]).filter(x=>kbMatch(x,q,['key','name','plate','contact_id','address_id','note']));
  }
  if(kind==='projects'){
    const q=document.getElementById('kbProjectSearch')?.value||'';
    return (kbMaster.projects||[]).filter(x=>kbMatch(x,q,['code','name','project_id','note']));
  }
  if(kind==='tags'){
    const q=document.getElementById('kbTagSearch')?.value||'';
    return (kbMaster.tags||[]).filter(x=>kbMatch(x,q,['tag_id','name','note']));
  }
  return [];
}
'''
marker = 'function kbRenderMaster(){'
if marker in html and 'function kbFiltered(kind)' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

# Replace the four table data sources with their filtered variants and show counts.
html = html.replace("(kbMaster.products||[]).map(x=>", "kbFiltered('products').map(x=>", 1)
html = html.replace("(kbMaster.associates||[]).map(x=>", "kbFiltered('associates').map(x=>", 1)
html = html.replace("(kbMaster.projects||[]).map(x=>", "kbFiltered('projects').map(x=>", 1)
html = html.replace("(kbMaster.tags||[]).map(x=>", "kbFiltered('tags').map(x=>", 1)

# Add count updates at the beginning of kbRenderMaster without restructuring it.
count_code = """const _kp=kbFiltered('products'),_ka=kbFiltered('associates'),_kj=kbFiltered('projects'),_kt=kbFiltered('tags');\n  const _c1=document.getElementById('kbProductCount'),_c2=document.getElementById('kbAssociateCount'),_c3=document.getElementById('kbProjectCount'),_c4=document.getElementById('kbTagCount');\n  if(_c1)_c1.textContent=_kp.length+' / '+(kbMaster.products||[]).length; if(_c2)_c2.textContent=_ka.length+' / '+(kbMaster.associates||[]).length; if(_c3)_c3.textContent=_kj.length+' / '+(kbMaster.projects||[]).length; if(_c4)_c4.textContent=_kt.length+' / '+(kbMaster.tags||[]).length;\n  """
if marker in html and "kbProductCount" in html and "_kp=kbFiltered('products')" not in html:
    html = html.replace(marker, marker + '\n  ' + count_code, 1)

core.HTML = html
print(f'[SAMA] KolayBi search filters active: panes={inserted}')
