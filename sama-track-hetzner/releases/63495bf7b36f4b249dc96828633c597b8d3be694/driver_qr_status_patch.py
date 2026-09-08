import base64
import hashlib
import hmac
import html
import os
import secrets
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

import print_audit_patch as print_patch

app = print_patch.app
core = print_patch.core

SECRET_FILE = Path(core.VOLUME_DIR) / '.driver_qr_secret'


def _secret() -> bytes:
    env = os.environ.get('SAMA_DRIVER_QR_SECRET', '').strip()
    if env:
        return env.encode('utf-8')
    try:
        if SECRET_FILE.exists():
            return SECRET_FILE.read_text(encoding='utf-8').strip().encode('utf-8')
        value = secrets.token_hex(32)
        SECRET_FILE.write_text(value, encoding='utf-8')
        return value.encode('utf-8')
    except Exception:
        # Last-resort process-local secret. Railway volume should normally make the
        # branch above persistent, but the app still starts if storage is read-only.
        return b'sama-driver-qr-fallback-v1'


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode('utf-8')).decode('ascii').rstrip('=')


def _unb64(text: str) -> str:
    pad = '=' * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode((text + pad).encode('ascii')).decode('utf-8')


def _token(scna: str) -> str:
    key = str(scna or '').strip().upper()
    payload = _b64(key)
    sig = hmac.new(_secret(), payload.encode('ascii'), hashlib.sha256).hexdigest()[:32]
    return payload + '.' + sig


def _token_scna(token: str) -> str:
    try:
        payload, sig = str(token or '').split('.', 1)
        expected = hmac.new(_secret(), payload.encode('ascii'), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            raise ValueError('bad signature')
        return _unb64(payload).strip().upper()
    except Exception:
        raise HTTPException(404, 'QR bağlantısı geçersiz.')


def _init_driver_status_db():
    c = core.db()
    try:
        c.execute('''
          CREATE TABLE IF NOT EXISTS driver_status_reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scna TEXT NOT NULL,
            plate TEXT DEFAULT '',
            driver_name TEXT DEFAULT '',
            reported_status TEXT NOT NULL,
            approved_status TEXT DEFAULT '',
            review_state TEXT DEFAULT 'PENDING',
            report_note TEXT DEFAULT '',
            reviewer_note TEXT DEFAULT '',
            gps_state TEXT DEFAULT '',
            gps_lat REAL,
            gps_lon REAL,
            reported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_at DATETIME,
            reviewed_by TEXT DEFAULT ''
          )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_driver_status_pending ON driver_status_reports(review_state,reported_at)')
        c.commit()
    finally:
        c.close()


@app.on_event('startup')
def _driver_status_startup():
    _init_driver_status_db()
    _secret()
    print('[SAMA] Driver QR status + tracker review pages active')


class DriverStatusIn(BaseModel):
    status: str
    note: str = ''


class DriverReviewIn(BaseModel):
    action: str
    approved_status: str = ''
    note: str = ''


VALID_DRIVER = {
    'WAITING': 'BEKLEMEDEYİM',
    'UNLOADING': 'BOŞALTIMDAYIM',
    'RETURNING': 'DÖNÜŞTEYİM',
}


@app.get('/api/driver-status/link/{scna}')
def driver_status_link(scna: str, request: Request):
    key = str(scna or '').strip().upper()
    c = core.db()
    try:
        row = c.execute('SELECT scna,plate FROM trips WHERE UPPER(TRIM(scna))=?', (key,)).fetchone()
    finally:
        c.close()
    if not row:
        raise HTTPException(404, 'Sevkiyat bulunamadı.')
    url = str(request.base_url).rstrip('/') + '/driver-status/' + _token(key)
    return {'ok': True, 'scna': key, 'plate': row['plate'], 'url': url}


@app.get('/api/driver-status/qr/{scna}')
def driver_status_qr(scna: str, request: Request):
    try:
        import qrcode
        from io import BytesIO
    except Exception:
        raise HTTPException(500, 'QR modülü yüklenemedi.')
    link = driver_status_link(scna, request)['url']
    img = qrcode.make(link)
    out = BytesIO()
    img.save(out, format='PNG')
    return Response(out.getvalue(), media_type='image/png', headers={'Cache-Control': 'no-store'})


@app.get('/driver-status/{token}', response_class=HTMLResponse)
def driver_status_page(token: str):
    scna = _token_scna(token)
    c = core.db()
    try:
        row = c.execute('''
          SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name,
                 COALESCE(a.name,'') area_name,COALESCE(cu.name,'') customer_name
          FROM trips t
          LEFT JOIN drivers d ON d.id=t.driver_id
          LEFT JOIN areas a ON a.id=t.area_id
          LEFT JOIN customers cu ON cu.id=t.customer_id
          WHERE UPPER(TRIM(t.scna))=?
        ''', (scna,)).fetchone()
    finally:
        c.close()
    if not row:
        raise HTTPException(404, 'Sevkiyat bulunamadı.')

    plate = html.escape(str(row['plate'] or ''))
    driver = html.escape(str(row['driver_name'] or ''))
    area = html.escape(str(row['area_name'] or ''))
    customer = html.escape(str(row['customer_name'] or ''))
    safe_token = html.escape(token, quote=True)
    safe_scna = html.escape(scna)

    return HTMLResponse(f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>SAMA DRIVER • {safe_scna}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(160deg,#07111f,#0b1d34 55%,#102a46);font-family:Arial,sans-serif;color:#fff;min-height:100vh}}.app{{max-width:560px;margin:auto;padding:22px 16px 34px}}.brand{{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}}.logo{{font-size:22px;font-weight:900;letter-spacing:.8px}}.live{{font-size:11px;padding:7px 10px;border:1px solid #315071;border-radius:999px;color:#a8c8e8;background:#10243a}}.trip{{background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.12);border-radius:22px;padding:18px;box-shadow:0 18px 55px rgba(0,0,0,.25);backdrop-filter:blur(8px)}}.scna{{color:#8ab4df;font-size:12px;font-weight:800;letter-spacing:1.4px}}.plate{{font-size:37px;font-weight:950;margin:5px 0 12px}}.meta{{display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;color:#c7d8ea}}.meta b{{display:block;color:#fff;font-size:13px;margin-top:2px}}h1{{font-size:20px;margin:23px 3px 12px}}.hint{{color:#9eb8d1;font-size:12px;margin:0 3px 14px;line-height:1.5}}.choices{{display:grid;gap:13px}}button{{width:100%;border:0;border-radius:22px;padding:0;overflow:hidden;color:#fff;text-align:left;box-shadow:0 14px 30px rgba(0,0,0,.25);cursor:pointer}}button:active{{transform:scale(.985)}}.choice{{display:flex;align-items:center;gap:17px;padding:20px}}.icon{{width:64px;height:64px;display:grid;place-items:center;border-radius:18px;background:rgba(255,255,255,.15);font-size:33px}}.ct{{font-size:21px;font-weight:950}}.cs{{font-size:11px;opacity:.82;margin-top:5px}}.wait{{background:linear-gradient(135deg,#d38a12,#b96909)}}.unload{{background:linear-gradient(135deg,#198754,#0c6940)}}.return{{background:linear-gradient(135deg,#1677c8,#0b579a)}}#msg{{display:none;margin-top:15px;padding:16px;border-radius:18px;background:#e9fff2;color:#0d5f34;font-weight:800;text-align:center}}.foot{{text-align:center;color:#6e8aa5;font-size:10px;margin-top:20px}}
</style></head><body><main class="app"><div class="brand"><div class="logo">SAMA <span style="color:#62aaf0">DRIVER</span></div><div class="live">QR STATUS</div></div><section class="trip"><div class="scna">SCNA {safe_scna}</div><div class="plate">{plate}</div><div class="meta"><div>ŞOFÖR<b>{driver or '-'}</b></div><div>BÖLGE<b>{area or '-'}</b></div><div style="grid-column:1/3">MÜŞTERİ<b>{customer or '-'}</b></div></div></section><h1>Şu an ne durumdasın?</h1><p class="hint">Sadece mevcut durumunu seç. Bildirimin operasyon/GPS takipçisine onay için gönderilecek.</p><div class="choices"><button class="wait" onclick="sendStatus('WAITING')"><div class="choice"><div class="icon">⏱️</div><div><div class="ct">BEKLEMEDEYİM</div><div class="cs">Yükleme / boşaltma / sıra bekliyorum</div></div></div></button><button class="unload" onclick="sendStatus('UNLOADING')"><div class="choice"><div class="icon">🏗️</div><div><div class="ct">BOŞALTIMDAYIM</div><div class="cs">Teslimat noktasında boşaltım yapılıyor</div></div></div></button><button class="return" onclick="sendStatus('RETURNING')"><div class="choice"><div class="icon">↩️</div><div><div class="ct">DÖNÜŞTEYİM</div><div class="cs">Boşaltım bitti, dönüş yolundayım</div></div></div></button></div><div id="msg"></div><div class="foot">SAMA TRACK • DRIVER STATUS</div></main><script>
let busy=false;async function sendStatus(s){{if(busy)return;if(!confirm('Durum bildirimi gönderilsin mi?'))return;busy=true;try{{const r=await fetch('/driver-status/{safe_token}/submit',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{status:s}})}});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Hata');document.querySelector('.choices').style.display='none';const m=document.getElementById('msg');m.style.display='block';m.innerHTML='✓ Bildirim gönderildi.<br><span style="font-size:12px;font-weight:600">GPS takipçisi onayladıktan sonra operasyon durumuna işlenecek.</span>';}}catch(e){{alert(e.message)}}finally{{busy=false}}}}
</script></body></html>''')


@app.post('/driver-status/{token}/submit')
def driver_status_submit(token: str, body: DriverStatusIn):
    scna = _token_scna(token)
    status = str(body.status or '').strip().upper()
    if status not in VALID_DRIVER:
        raise HTTPException(400, 'Geçersiz durum.')
    c = core.db()
    try:
        row = c.execute('''SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name FROM trips t LEFT JOIN drivers d ON d.id=t.driver_id WHERE UPPER(TRIM(t.scna))=?''', (scna,)).fetchone()
        if not row:
            raise HTTPException(404, 'Sevkiyat bulunamadı.')
        # Do not let repeated nervous tapping manufacture a queue avalanche.
        recent = c.execute('''SELECT id FROM driver_status_reports WHERE scna=? AND reported_status=? AND review_state='PENDING' AND datetime(reported_at)>=datetime('now','-10 minutes') ORDER BY id DESC LIMIT 1''', (scna,status)).fetchone()
        if recent:
            return {'ok': True, 'duplicate': True, 'id': recent['id']}
        cur = c.execute('''INSERT INTO driver_status_reports(scna,plate,driver_name,reported_status,report_note) VALUES(?,?,?,?,?)''', (scna,row['plate'],row['driver_name'],status,str(body.note or '').strip()))
        c.commit()
        rid = cur.lastrowid
    finally:
        c.close()
    return {'ok': True, 'id': rid, 'scna': scna, 'status': status}


@app.get('/api/driver-status/reports')
def driver_status_reports(state: str = 'PENDING'):
    st = str(state or 'PENDING').strip().upper()
    c = core.db()
    try:
        rows = c.execute('''SELECT * FROM driver_status_reports WHERE review_state=? ORDER BY id DESC LIMIT 200''', (st,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


@app.post('/api/driver-status/reports/{report_id}/review')
def driver_status_review(report_id: int, body: DriverReviewIn, request: Request):
    action = str(body.action or '').strip().upper()
    if action not in ('APPROVE','REJECT'):
        raise HTTPException(400, 'İşlem APPROVE veya REJECT olmalı.')
    c = core.db()
    try:
        row = c.execute('SELECT * FROM driver_status_reports WHERE id=?', (report_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Bildirim bulunamadı.')
        if row['review_state'] != 'PENDING':
            raise HTTPException(409, 'Bu bildirim daha önce değerlendirildi.')
        approved = str(body.approved_status or row['reported_status'] or '').strip().upper()
        if approved not in VALID_DRIVER:
            approved = row['reported_status']
        user = getattr(request.state, 'auth_user', None) or {}
        reviewer = str(user.get('full_name') or user.get('username') or '').strip()
        new_state = 'APPROVED' if action == 'APPROVE' else 'REJECTED'
        c.execute('''UPDATE driver_status_reports SET review_state=?,approved_status=?,reviewer_note=?,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=? WHERE id=?''', (new_state, approved if action=='APPROVE' else '', str(body.note or '').strip(), reviewer, report_id))
        if action == 'APPROVE':
            label = VALID_DRIVER.get(approved, approved)
            # Keep the established operation state machine intact. The approved
            # driver signal is written into operation_note and can later be mapped
            # to AWZARTECH/Teltonika-confirmed states without breaking old reports.
            c.execute('''INSERT INTO vehicle_operations(plate,operation_note,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(plate) DO UPDATE SET operation_note=excluded.operation_note,updated_at=CURRENT_TIMESTAMP''', (row['plate'], 'ŞOFÖR QR: ' + label))
        c.commit()
    finally:
        c.close()
    return {'ok': True, 'review_state': new_state, 'approved_status': approved if action=='APPROVE' else ''}


@app.get('/driver-status-monitor', response_class=HTMLResponse)
def driver_status_monitor_page():
    return HTMLResponse('''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SAMA • GPS Takipçi Bildirimleri</title><style>
*{box-sizing:border-box}body{margin:0;background:#07111f;color:#eaf2fb;font-family:Arial,sans-serif}.page{max-width:1180px;margin:auto;padding:25px}.top{display:flex;justify-content:space-between;align-items:center;gap:15px;margin-bottom:20px}.title{font-size:28px;font-weight:950}.sub{color:#7896b4;font-size:12px;margin-top:5px}.refresh{border:1px solid #274665;background:#102238;color:#dcecff;padding:11px 15px;border-radius:12px;cursor:pointer}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px}.stat{background:#0d1c2d;border:1px solid #1d3853;border-radius:17px;padding:15px}.stat b{font-size:24px;display:block}.stat span{font-size:11px;color:#7796b5}.grid{display:grid;gap:13px}.card{background:#0d1b2b;border:1px solid #1d3853;border-radius:20px;padding:17px;display:grid;grid-template-columns:1.35fr 1fr 1.1fr auto;gap:15px;align-items:center}.plate{font-size:25px;font-weight:950}.scna{font-size:11px;color:#7fa2c4}.driver{font-size:13px;color:#c8d8e8;margin-top:5px}.status{font-size:14px;font-weight:900;padding:10px 12px;border-radius:12px;display:inline-block}.WAITING{background:#3f2a0b;color:#ffc663}.UNLOADING{background:#0d3928;color:#62dfa7}.RETURNING{background:#0b3153;color:#6ab8ff}.gps{background:#0a1624;border:1px dashed #284967;border-radius:14px;padding:10px;font-size:11px;color:#7899b8}.gps b{display:block;color:#d9e8f7;font-size:12px;margin-bottom:4px}.time{font-size:11px;color:#7894af;margin-top:5px}.actions{display:flex;gap:7px}.actions button{border:0;border-radius:11px;padding:11px 13px;font-weight:850;cursor:pointer}.ok{background:#19a564;color:#fff}.edit{background:#1e6fb5;color:#fff}.no{background:#b43a3a;color:#fff}.empty{text-align:center;border:1px dashed #29455f;border-radius:20px;padding:55px;color:#66849f}@media(max-width:850px){.card{grid-template-columns:1fr}.stats{grid-template-columns:1fr}.actions{justify-content:flex-start}}</style></head><body><main class="page"><div class="top"><div><div class="title">GPS TAKİPÇİ • ŞOFÖR BİLDİRİMLERİ</div><div class="sub">QR bildirimleri burada onay bekler. Şoförün tıklaması tek başına operasyon gerçeği sayılmaz, neyse ki.</div></div><button class="refresh" onclick="load()">↻ YENİLE</button></div><div class="stats"><div class="stat"><b id="pending">0</b><span>ONAY BEKLEYEN</span></div><div class="stat"><b>15 sn</b><span>OTOMATİK YENİLEME</span></div><div class="stat"><b>GPS</b><span>API BAĞLANTISI İÇİN HAZIR</span></div></div><div id="grid" class="grid"></div></main><script>
const labels={WAITING:'BEKLEMEDEYİM',UNLOADING:'BOŞALTIMDAYIM',RETURNING:'DÖNÜŞTEYİM'};function esc(s){return String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}async function api(u,o){const r=await fetch(u,o);let j={};try{j=await r.json()}catch{}if(!r.ok)throw new Error(j.detail||('HTTP '+r.status));return j}async function load(){try{const rows=await api('/api/driver-status/reports?state=PENDING');pending.textContent=rows.length;grid.innerHTML=rows.length?rows.map(x=>`<div class="card"><div><div class="scna">SCNA ${esc(x.scna)}</div><div class="plate">${esc(x.plate)}</div><div class="driver">${esc(x.driver_name||'-')}</div></div><div><span class="status ${esc(x.reported_status)}">${esc(labels[x.reported_status]||x.reported_status)}</span><div class="time">${esc(x.reported_at||'')}</div></div><div class="gps"><b>GPS KONTROLÜ</b>${x.gps_state?esc(x.gps_state):'Canlı GPS API henüz bağlı değil. Takipçi mevcut GPS ekranından teyit eder.'}</div><div class="actions"><button class="ok" onclick="review(${x.id},'APPROVE','${esc(x.reported_status)}')">ONAYLA</button><button class="edit" onclick="change(${x.id},'${esc(x.reported_status)}')">DÜZELT</button><button class="no" onclick="review(${x.id},'REJECT','')">REDDET</button></div></div>`).join(''):'<div class="empty">Bekleyen şoför bildirimi yok.</div>'}catch(e){grid.innerHTML='<div class="empty">'+esc(e.message)+'</div>'}}async function review(id,action,status){let note='';if(action==='REJECT')note=prompt('Red nedeni (opsiyonel):')||'';try{await api('/api/driver-status/reports/'+id+'/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:action,approved_status:status,note:note})});load()}catch(e){alert(e.message)}}function change(id,current){const opts='WAITING = BEKLEMEDEYİM\nUNLOADING = BOŞALTIMDAYIM\nRETURNING = DÖNÜŞTEYİM';const s=(prompt('Onaylanacak doğru durum:\n'+opts,current)||'').trim().toUpperCase();if(!labels[s])return;review(id,'APPROVE',s)}load();setInterval(load,15000);
</script></body></html>''')
