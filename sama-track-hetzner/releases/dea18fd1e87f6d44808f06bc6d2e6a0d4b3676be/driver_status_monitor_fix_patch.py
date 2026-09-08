from fastapi.responses import HTMLResponse
import print_qr_driver_link_patch as qrpatch

app = qrpatch.app
core = qrpatch.base.core


def _monitor_page_fixed():
    return HTMLResponse(r'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SAMA • Şoför Bildirimleri</title><style>
*{box-sizing:border-box}body{margin:0;background:#081522;color:#fff;font-family:Arial,sans-serif}.wrap{max-width:1100px;margin:auto;padding:20px}.head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}.title{font-size:24px;font-weight:900}.sub{font-size:12px;color:#98aec3}.pill{background:#15314b;border:1px solid #284a67;border-radius:999px;padding:9px 13px;font-size:12px}.err{display:none;background:#6b1b1b;border:1px solid #a84545;padding:12px;border-radius:12px;margin-bottom:12px}.empty{background:#102337;border:1px dashed #34516a;border-radius:16px;padding:40px;text-align:center;color:#9fb5c8}.grid{display:grid;gap:12px}.card{display:grid;grid-template-columns:90px 1fr auto;gap:14px;align-items:center;background:#102337;border:1px solid #274057;border-radius:18px;padding:14px}.ico{width:78px;height:78px;border-radius:16px;display:grid;place-items:center;font-size:38px;font-weight:900}.wait{background:#e8a21b}.unload{background:#36a85a}.return{background:#2f86d1}.scna{font-size:12px;color:#8fb5d5;font-weight:800}.plate{font-size:25px;font-weight:950;margin:3px 0}.meta{font-size:12px;color:#c1d1df;line-height:1.6}.status{font-size:16px;font-weight:900;margin-bottom:8px}.actions{display:flex;gap:8px;flex-wrap:wrap}.actions button{border:0;border-radius:10px;padding:10px 14px;color:#fff;font-weight:900;cursor:pointer}.ok{background:#2c9b50}.no{background:#d04b42}.refresh{background:#31536d}@media(max-width:700px){.card{grid-template-columns:68px 1fr}.ico{width:60px;height:60px}.right{grid-column:1/3}.head{align-items:flex-start;flex-direction:column}}
</style></head><body><main class="wrap"><div class="head"><div><div class="title">ŞOFÖR BİLDİRİMLERİ</div><div class="sub">QR üzerinden gelen bildirimler • otomatik 10 saniyede yenilenir</div></div><div class="pill" id="count">0 BEKLİYOR</div></div><div id="err" class="err"></div><div id="list" class="grid"><div class="empty">Bildirimler yükleniyor...</div></div></main><script>
const labels={WAITING:'BEKLEME',UNLOADING:'BOŞALTIM',RETURNING:'DÖNÜŞ'};const icons={WAITING:'⏱️',UNLOADING:'🚚⬆️',RETURNING:'↩️🚚'};const cls={WAITING:'wait',UNLOADING:'unload',RETURNING:'return'};
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function load(){const e=document.getElementById('err');e.style.display='none';try{const r=await fetch('/api/driver-status/reports?state=PENDING',{credentials:'same-origin',cache:'no-store'});const j=await r.json();if(!r.ok)throw new Error(j.detail||('HTTP '+r.status));document.getElementById('count').textContent=j.length+' BEKLİYOR';const box=document.getElementById('list');if(!j.length){box.innerHTML='<div class="empty">Şu anda bekleyen şoför bildirimi yok.</div>';return}box.innerHTML=j.map(x=>`<article class="card"><div class="ico ${cls[x.reported_status]||''}">${icons[x.reported_status]||'🚚'}</div><div><div class="scna">SCNA ${esc(x.scna)}</div><div class="plate">${esc(x.plate)}</div><div class="meta">Şoför: <b>${esc(x.driver_name||'-')}</b><br>Bildirim zamanı: ${esc(x.reported_at||'')}</div></div><div class="right"><div class="status">${labels[x.reported_status]||esc(x.reported_status)}</div><div class="actions"><button class="ok" onclick="review(${Number(x.id)},'APPROVE')">✓ ONAYLA</button><button class="no" onclick="review(${Number(x.id)},'REJECT')">✕ REDDET</button><button class="refresh" onclick="load()">↻ YENİLE</button></div></div></article>`).join('')}catch(err){e.textContent='Bildirimler alınamadı: '+err.message+' • Bu sayfayı SAMA TRACK hesabına giriş yaptığınız aynı tarayıcıda açın.';e.style.display='block';document.getElementById('list').innerHTML='<div class="empty">Bağlantı / oturum kontrol ediliyor.</div>'}}
async function review(id,action){if(!confirm(action==='APPROVE'?'Bildirim onaylansın mı?':'Bildirim reddedilsin mi?'))return;try{const r=await fetch('/api/driver-status/reports/'+id+'/review',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Hata');await load()}catch(e){alert(e.message)}}
load();setInterval(load,10000);
</script></body></html>''')

# Replace the previous standalone monitor route in-place.
for route in app.routes:
    if getattr(route,'path',None)=='/driver-status-monitor' and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint=_monitor_page_fixed
        if getattr(route,'dependant',None) is not None:
            route.dependant.call=_monitor_page_fixed
        break

# Put a visible launcher into the main application without adding another JS block.
html = core.HTML
launcher = '''<button type="button" onclick="window.open('/driver-status-monitor','_blank')" style="position:fixed;right:18px;bottom:18px;z-index:99999;background:#dc2626;color:#fff;border:0;border-radius:16px;padding:13px 18px;font-weight:900;box-shadow:0 8px 24px #0005;cursor:pointer">🔔 ŞOFÖR BİLDİRİMLERİ</button>'''
if 'ŞOFÖR BİLDİRİMLERİ</button>' not in html:
    if '</body>' in html:
        html = html.replace('</body>', launcher + '</body>', 1)
    else:
        html += launcher
core.HTML = html

print('[SAMA] Driver notification monitor fixed + visible launcher active')
