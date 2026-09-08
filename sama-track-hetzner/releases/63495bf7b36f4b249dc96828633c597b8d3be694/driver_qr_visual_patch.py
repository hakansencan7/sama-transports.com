import html
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
import driver_qr_status_patch as base

app = base.app
core = base.core


def _visual_driver_page(token: str):
    scna = base._token_scna(token)
    c = core.db()
    try:
        row = c.execute('''SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name FROM trips t LEFT JOIN drivers d ON d.id=t.driver_id WHERE UPPER(TRIM(t.scna))=?''',(scna,)).fetchone()
    finally:
        c.close()
    if not row:
        raise HTTPException(404,'Sevkiyat bulunamadı.')

    safe_token = html.escape(token, quote=True)
    plate = html.escape(str(row['plate'] or ''))
    safe_scna = html.escape(scna)

    return HTMLResponse(f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>SAMA DRIVER</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#eef2f6;font-family:Arial,sans-serif;color:#0b1420}}main{{max-width:520px;margin:auto;padding:12px}}.top{{display:flex;justify-content:space-between;align-items:center;margin:2px 2px 10px}}.brand{{font-weight:950;font-size:20px}}.tag{{font-size:11px;font-weight:900;background:#101c2c;color:#fff;border-radius:999px;padding:7px 10px}}.trip{{background:#fff;border:2px solid #d4dde8;border-radius:18px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}.trip b{{font-size:27px}}.scna{{font-size:11px;color:#617187;font-weight:900}}.instruction{{text-align:center;font-size:17px;font-weight:950;margin:8px 0 10px}}.choices{{display:grid;gap:10px}}button{{width:100%;border:0;border-radius:24px;padding:8px;min-height:170px;box-shadow:0 8px 20px rgba(15,23,42,.13);cursor:pointer;touch-action:manipulation}}button:active{{transform:scale(.985)}}.pic{{display:grid;grid-template-columns:155px 1fr;align-items:center;gap:10px}}.iconbox{{height:150px;border-radius:18px;background:#fff;display:grid;place-items:center;border:3px solid rgba(0,0,0,.12)}}svg{{width:140px;height:140px}}.label{{font-weight:950;font-size:27px;text-align:left;color:#08111c;line-height:1}}.arabic{{font-weight:900;font-size:20px;text-align:left;color:#08111c;direction:rtl;margin-top:8px}}.mini{{font-size:12px;font-weight:900;text-align:left;margin-top:7px;color:#223246}}.wait{{background:#ffb21a}}.unload{{background:#55bd67}}.return{{background:#4a9fe9}}.legend{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px}}.legend div{{background:#fff;border:1px solid #d7e0ea;border-radius:12px;text-align:center;padding:8px 4px;font-size:11px;font-weight:900}}#done{{display:none;background:#fff;border:4px solid #43a85b;border-radius:26px;padding:36px 18px;text-align:center;margin-top:12px}}#done .tick{{font-size:82px}}#done b{{display:block;font-size:27px;margin-top:4px}}#done .truck{{font-size:56px;margin-top:10px}}.foot{{text-align:center;color:#7b8795;font-size:10px;margin-top:12px}}@media(max-width:390px){{button{{min-height:154px}}.pic{{grid-template-columns:135px 1fr}}.iconbox{{height:134px}}svg{{width:126px;height:126px}}.label{{font-size:24px}}.arabic{{font-size:18px}}}}
</style></head><body><main><div class="top"><div class="brand">SAMA DRIVER</div><div class="tag">QR</div></div><div class="trip"><div><div class="scna">SCNA {safe_scna}</div><b>{plate}</b></div><div style="font-size:38px">🚛</div></div><div class="instruction">👇 SADECE RESME DOKUN</div><div id="choices" class="choices">

<button class="wait" data-status="WAITING" aria-label="Beklemedeyim"><div class="pic"><div class="iconbox"><svg viewBox="0 0 160 160" aria-hidden="true"><rect x="18" y="92" width="90" height="30" rx="6" fill="#111"/><rect x="98" y="101" width="25" height="21" rx="4" fill="#111"/><circle cx="42" cy="128" r="13" fill="#111"/><circle cx="102" cy="128" r="13" fill="#111"/><circle cx="124" cy="42" r="26" fill="none" stroke="#111" stroke-width="8"/><path d="M124 27v17l13 9" fill="none" stroke="#111" stroke-width="7" stroke-linecap="round"/><path d="M17 54h57" stroke="#111" stroke-width="9" stroke-linecap="round"/><path d="M17 70h40" stroke="#111" stroke-width="9" stroke-linecap="round"/></svg></div><div><div class="label">BEKLE</div><div class="arabic">انتظار</div><div class="mini">⏱️ KAMYON DURUYOR</div></div></div></button>

<button class="unload" data-status="UNLOADING" aria-label="Boşaltımdayım"><div class="pic"><div class="iconbox"><svg viewBox="0 0 160 160" aria-hidden="true"><circle cx="42" cy="128" r="13" fill="#111"/><circle cx="112" cy="128" r="13" fill="#111"/><rect x="24" y="105" width="104" height="17" rx="4" fill="#111"/><rect x="105" y="86" width="25" height="25" rx="4" fill="#111"/><path d="M35 96L92 34l14 11-43 57z" fill="#111"/><path d="M38 91l12-42 47 8-35 42z" fill="#111"/><circle cx="118" cy="46" r="5" fill="#111"/><circle cx="132" cy="58" r="6" fill="#111"/><circle cx="142" cy="72" r="7" fill="#111"/><path d="M119 37l28 39" stroke="#111" stroke-width="4" stroke-dasharray="4 6"/></svg></div><div><div class="label">BOŞALT</div><div class="arabic">تفريغ</div><div class="mini">⬆️ DAMPER KALKIK</div></div></div></button>

<button class="return" data-status="RETURNING" aria-label="Dönüşteyim"><div class="pic"><div class="iconbox"><svg viewBox="0 0 160 160" aria-hidden="true"><rect x="30" y="91" width="76" height="30" rx="6" fill="#111"/><rect x="99" y="100" width="28" height="21" rx="4" fill="#111"/><circle cx="49" cy="128" r="13" fill="#111"/><circle cx="108" cy="128" r="13" fill="#111"/><path d="M132 43H67c-20 0-31 14-31 30" fill="none" stroke="#111" stroke-width="10" stroke-linecap="round"/><path d="M72 25L50 43l22 18" fill="none" stroke="#111" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/></svg></div><div><div class="label">DÖNÜŞ</div><div class="arabic">عودة</div><div class="mini">↩️ GERİ GELİYORUM</div></div></div></button>

</div><div class="legend"><div>🟧 ⏱️<br>BEKLE</div><div>🟩 ⬆️<br>BOŞALT</div><div>🟦 ↩️<br>DÖNÜŞ</div></div><div id="done"><div class="tick">✅</div><b>TAMAM</b><div class="truck">🚛</div></div><div class="foot">SAMA TRACK</div></main><script>
let busy=false;const speak=t=>{{try{{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(t);u.lang='tr-TR';u.rate=.82;u.volume=1;speechSynthesis.speak(u)}}catch(e){{}}}};async function send(s){{if(busy)return;busy=true;const spoken=s==='WAITING'?'Beklemedeyim':s==='UNLOADING'?'Boşaltımdayım':'Dönüşteyim';speak(spoken);try{{const r=await fetch('/driver-status/{safe_token}/submit',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{status:s}})}});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Hata');document.getElementById('choices').style.display='none';document.querySelector('.legend').style.display='none';document.querySelector('.instruction').style.display='none';document.getElementById('done').style.display='block';speak('Tamam. Bildirim gönderildi');if(navigator.vibrate)navigator.vibrate([180,90,180]);}}catch(e){{busy=false;alert(e.message)}}}}document.querySelectorAll('[data-status]').forEach(b=>b.addEventListener('click',()=>send(b.dataset.status)));
</script></body></html>''')

for route in app.routes:
    if getattr(route,'path',None)=='/driver-status/{token}' and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint=_visual_driver_page
        if getattr(route,'dependant',None) is not None:
            route.dependant.call=_visual_driver_page
        break

print('[SAMA] Driver QR visual UX V2 active: big pictograms + Arabic cues')
