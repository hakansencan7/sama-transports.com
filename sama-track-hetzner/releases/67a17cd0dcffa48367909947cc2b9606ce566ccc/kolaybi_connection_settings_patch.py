import os
from fastapi import Request, HTTPException
import kolaybi_send_patch as send

app = send.app
core = send.core
sync = send.base
kdb = send.kdb
html = core.HTML

# Keep credentials out of GitHub. Railway env wins only when it is actually non-empty;
# persistent /data DB is the web-panel fallback.
c = kdb()
try:
    c.execute('''CREATE TABLE IF NOT EXISTS connection_settings(
      key TEXT PRIMARY KEY,
      value TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.commit()
finally:
    c.close()


def _read_settings():
    c = kdb()
    try:
        rows = c.execute('SELECT key,value FROM connection_settings').fetchall()
        return {str(r['key']): str(r['value'] or '') for r in rows}
    finally:
        c.close()


def _clean_env(name):
    return str(os.getenv(name) or '').strip()


def _pick(env_name, saved, key):
    env_value = _clean_env(env_name)
    if env_value:
        return env_value, 'ENV'
    db_value = str(saved.get(key) or '').strip()
    if db_value:
        return db_value, 'DB'
    return '', ''


def _apply_settings():
    saved = _read_settings()
    # A Railway variable that exists but is blank/whitespace must NOT block the DB fallback.
    base_url, base_src = _pick('KOLAYBI_BASE_URL', saved, 'base_url')
    api_key, api_src = _pick('KOLAYBI_API_KEY', saved, 'api_key')
    channel, channel_src = _pick('KOLAYBI_CHANNEL', saved, 'channel')
    if base_url and not base_url.startswith('http'):
        base_url = 'https://' + base_url
    if base_url and not base_url.rstrip('/').endswith('/kolaybi/v1'):
        base_url = base_url.rstrip('/') + '/kolaybi/v1'
    sync.BASE_URL = base_url.rstrip('/')
    sync.API_KEY = api_key
    sync.CHANNEL = channel
    sync._TOKEN = ''
    sync._TOKEN_TIME = 0.0
    return {
        'base_url': sync.BASE_URL,
        'api_key': sync.API_KEY,
        'channel': sync.CHANNEL,
        'source': {'base_url': base_src, 'api_key': api_src, 'channel': channel_src},
    }


_apply_settings()


@app.get('/api/kolaybi/settings')
def kb_get_settings():
    cfg = _apply_settings()
    return {
        'configured': bool(cfg['base_url'] and cfg['api_key'] and cfg['channel']),
        'base_url': cfg['base_url'],
        'channel': cfg['channel'],
        'api_key_set': bool(cfg['api_key']),
        'api_key_masked': (cfg['api_key'][:5] + '••••••' + cfg['api_key'][-4:]) if len(cfg['api_key']) >= 10 else ('••••••' if cfg['api_key'] else ''),
        'source': cfg['source'],
        'saved_db': {k: bool(str(v or '').strip()) for k,v in _read_settings().items()},
    }


@app.post('/api/kolaybi/settings')
async def kb_save_settings(request: Request):
    sync.base._admin_required()
    b = await request.json()
    current = _read_settings()
    base_url = str(b.get('base_url') or '').strip()
    channel = str(b.get('channel') or '').strip()
    api_key = str(b.get('api_key') or '').strip()
    # Empty API key means keep the previously saved secret.
    if not api_key:
        api_key = str(current.get('api_key') or '').strip()
    if not base_url or not channel or not api_key:
        raise HTTPException(status_code=400, detail='Base URL, Channel ve API Key zorunlu.')
    c = kdb()
    try:
        for key, value in [('base_url', base_url), ('channel', channel), ('api_key', api_key)]:
            c.execute('''INSERT INTO connection_settings(key,value,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP''', (key, value))
        c.commit()
    finally:
        c.close()
    cfg = _apply_settings()
    if not (cfg['base_url'] and cfg['api_key'] and cfg['channel']):
        raise HTTPException(status_code=500, detail='Ayarlar DB’ye kaydedildi fakat aktif bağlantıya uygulanamadı.')
    return {'ok': True, 'configured': True, 'source': cfg['source']}


@app.post('/api/kolaybi/test-connection')
def kb_test_connection():
    sync.base._admin_required()
    cfg = _apply_settings()
    missing=[]
    if not cfg['base_url']: missing.append('BASE URL')
    if not cfg['api_key']: missing.append('API KEY')
    if not cfg['channel']: missing.append('CHANNEL')
    if missing:
        raise HTTPException(status_code=400, detail='KolayBi bağlantı ayarları eksik: ' + ', '.join(missing))
    try:
        token = sync._token()
        tests = {}
        for kind, path in [('associates','associates'), ('products','products'), ('projects','projects'), ('tags','tags')]:
            try:
                resp = sync._get(path, {'per_page': 5})
                tests[kind] = {'ok': True, 'sample_count': len(sync._rows(resp))}
            except Exception as e:
                tests[kind] = {'ok': False, 'error': str(e)[:500]}
        return {'ok': True, 'token_ok': bool(token), 'tests': tests, 'source': cfg['source']}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'KolayBi bağlantı testi başarısız: {e}')


# Add connection card to existing KolayBi panel.
anchor = '<div class="kb-syncbar">'
card = r'''<div class="calc" style="margin-bottom:12px">
  <b>KOLAYBI BAĞLANTI AYARLARI</b>
  <div class="grid" style="margin-top:8px">
    <div class="field wide"><label>BASE URL</label><input id="kbBaseUrl" placeholder="https://.../kolaybi/v1"></div>
    <div class="field"><label>CHANNEL</label><input id="kbChannel"></div>
    <div class="field"><label>API KEY</label><input id="kbApiKey" type="password" placeholder="Kayıtlıysa boş bırakabilirsin"></div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
    <button class="btn primary" onclick="kbSaveConnection()">BAĞLANTIYI KAYDET</button>
    <button class="btn secondary" onclick="kbTestConnection()">BAĞLANTIYI TEST ET</button>
    <span id="kbConnectionState" class="section-note"></span>
  </div>
</div>'''
if anchor in html and 'id="kbBaseUrl"' not in html:
    html = html.replace(anchor, card + '\n  ' + anchor, 1)

helper = r'''
async function kbLoadConnection(){
  try{
    const x=await api('/api/kolaybi/settings');
    const u=document.getElementById('kbBaseUrl'),c=document.getElementById('kbChannel'),s=document.getElementById('kbConnectionState');
    if(u)u.value=x.base_url||''; if(c)c.value=x.channel||'';
    const src=x.source||{};
    const srcTxt=[src.base_url,src.channel,src.api_key].filter(Boolean).join('/');
    if(s)s.innerHTML=x.configured?'<span class="kb-ready">✓ BAĞLANTI AYARLARI HAZIR'+(srcTxt?' ['+kbEsc(srcTxt)+']':'')+'</span>':'<span class="kb-missing">BAĞLANTI AYARLARI EKSİK</span>';
  }catch(e){}
}
async function kbSaveConnection(){
  const s=document.getElementById('kbConnectionState');if(s)s.textContent='KAYDEDİLİYOR...';
  try{
    const r=await api('/api/kolaybi/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base_url:kbBaseUrl.value,channel:kbChannel.value,api_key:kbApiKey.value})});
    kbApiKey.value=''; if(s)s.innerHTML='<span class="kb-ready">✓ KAYDEDİLDİ</span>'; await kbLoadConnection();
  }catch(e){if(s)s.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
async function kbTestConnection(){
  const s=document.getElementById('kbConnectionState');if(s)s.textContent='TEST EDİLİYOR...';
  try{
    const r=await api('/api/kolaybi/test-connection',{method:'POST'});
    const bad=Object.entries(r.tests||{}).filter(([k,v])=>!v.ok).map(([k,v])=>k+': '+(v.error||'hata'));
    if(s)s.innerHTML=bad.length?'<span class="kb-missing">TOKEN OK | '+kbEsc(bad.join(' | '))+'</span>':'<span class="kb-ready">✓ TOKEN + KAYNAKLAR OK</span>';
  }catch(e){if(s)s.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
'''
marker = 'async function kbSyncAll(){'
if marker in html and 'async function kbTestConnection' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

# Ensure loading the KolayBi panel also loads connection status.
html = html.replace("show('kolaybi',this);loadKolaybiMaster()", "show('kolaybi',this);loadKolaybiMaster();kbLoadConnection()", 1)

core.HTML = html
cfg=_apply_settings()
print(f'[SAMA] KolayBi connection settings active: configured={bool(cfg["base_url"] and cfg["api_key"] and cfg["channel"])} source={cfg["source"]}')
