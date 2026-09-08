import re
import driver_status_monitor_fix_patch as monitor

app = monitor.app
core = monitor.core
html = core.HTML

# Remove older temporary/fallback launchers so we do not accumulate buttons.
html = re.sub(r'<button\b[^>]*onclick="window\.open\(\'/driver-status-monitor\',\'_blank\'\)"[^>]*>.*?</button>', '', html, flags=re.IGNORECASE|re.DOTALL)

# Add the launcher dynamically into the visible Operations area at runtime.
# This avoids matching translation dictionaries or hidden template text in the raw HTML.
helper = r'''
let samaDriverStatusLastCount=null;
let samaDriverStatusAudioCtx=null;
let samaDriverStatusSoundEnabled=localStorage.getItem('samaDriverStatusSound')==='1';

function samaDriverStatusEnsureAudio(){
  try{
    if(!samaDriverStatusAudioCtx){
      const Ctx=window.AudioContext||window.webkitAudioContext;
      if(Ctx)samaDriverStatusAudioCtx=new Ctx();
    }
    if(samaDriverStatusAudioCtx && samaDriverStatusAudioCtx.state==='suspended'){
      samaDriverStatusAudioCtx.resume().catch(()=>{});
    }
  }catch(_e){}
}

function samaDriverStatusBeep(){
  if(!samaDriverStatusSoundEnabled)return;
  try{
    samaDriverStatusEnsureAudio();
    const ctx=samaDriverStatusAudioCtx;
    if(!ctx || ctx.state!=='running')return;
    const now=ctx.currentTime;
    [0,.28,.56].forEach((delay,i)=>{
      const osc=ctx.createOscillator();
      const gain=ctx.createGain();
      osc.type='sine';
      osc.frequency.value=i===1?980:760;
      gain.gain.setValueAtTime(0.0001,now+delay);
      gain.gain.exponentialRampToValueAtTime(0.32,now+delay+.015);
      gain.gain.exponentialRampToValueAtTime(0.0001,now+delay+.19);
      osc.connect(gain);gain.connect(ctx.destination);
      osc.start(now+delay);osc.stop(now+delay+.21);
    });
  }catch(_e){}
}

function samaDriverStatusUpdateSoundButton(){
  const s=document.getElementById('samaDriverStatusSoundBtn');
  if(!s)return;
  s.innerHTML=samaDriverStatusSoundEnabled?'🔊 BİLDİRİM SESİ AÇIK':'🔇 BİLDİRİM SESİ KAPALI';
  s.style.background=samaDriverStatusSoundEnabled?'#166534':'#374151';
  s.style.borderColor=samaDriverStatusSoundEnabled?'#22c55e':'#6b7280';
}

function samaDriverStatusToggleSound(){
  samaDriverStatusSoundEnabled=!samaDriverStatusSoundEnabled;
  localStorage.setItem('samaDriverStatusSound',samaDriverStatusSoundEnabled?'1':'0');
  if(samaDriverStatusSoundEnabled){
    samaDriverStatusEnsureAudio();
    setTimeout(samaDriverStatusBeep,80);
  }
  samaDriverStatusUpdateSoundButton();
}

function samaInstallDriverStatusOperationsButton(){
  if(document.getElementById('samaDriverStatusOpsBtn')) return;
  const all=[...document.querySelectorAll('button,a,[role="button"],.menu-item,.nav-item,.sidebar-item,.card')];
  const norm=s=>String(s||'').replace(/\s+/g,' ').trim().toLocaleUpperCase('tr-TR');
  let anchor=all.find(el=>{
    const t=norm(el.innerText||el.textContent||'');
    return t==='OPERASYON MERKEZİ' || t==='OPERASYON MERKEZI' || t==='OPERATIONS CENTER';
  });
  if(!anchor){
    anchor=all.find(el=>{
      const t=norm(el.innerText||el.textContent||'');
      return t.includes('OPERASYON') && !t.includes('ŞOFÖR BİLDİRİMLERİ');
    });
  }

  const wrap=document.createElement('span');
  wrap.id='samaDriverStatusOpsWrap';
  wrap.style.cssText='display:inline-flex;gap:7px;align-items:center;flex-wrap:wrap;margin:6px 0;';

  const b=document.createElement('button');
  b.id='samaDriverStatusOpsBtn';
  b.type='button';
  b.innerHTML='🔔 ŞOFÖR BİLDİRİMLERİ <span id="samaDriverStatusOpsCount" style="display:inline-block;min-width:22px;margin-left:6px;padding:2px 7px;border-radius:999px;background:#ef4444;color:#fff;font-weight:900">0</span>';
  b.style.cssText='background:#7f1d1d;color:#fff;border:2px solid #ef4444;border-radius:12px;padding:10px 14px;font-weight:950;cursor:pointer;';
  b.addEventListener('click',()=>window.open('/driver-status-monitor','_blank'));

  const s=document.createElement('button');
  s.id='samaDriverStatusSoundBtn';
  s.type='button';
  s.style.cssText='color:#fff;border:2px solid #6b7280;border-radius:12px;padding:10px 12px;font-weight:900;cursor:pointer;';
  s.addEventListener('click',samaDriverStatusToggleSound);

  wrap.appendChild(b);wrap.appendChild(s);
  samaDriverStatusUpdateSoundButton();

  if(anchor && anchor.parentElement){
    anchor.insertAdjacentElement('afterend',wrap);
  }else{
    wrap.style.position='fixed';wrap.style.right='18px';wrap.style.bottom='18px';wrap.style.zIndex='99999';
    document.body.appendChild(wrap);
  }
  samaRefreshDriverStatusOpsCount();
}

async function samaRefreshDriverStatusOpsCount(){
  const badge=document.getElementById('samaDriverStatusOpsCount');
  if(!badge)return;
  try{
    const r=await fetch('/api/driver-status/reports?state=PENDING',{credentials:'same-origin',cache:'no-store'});
    if(!r.ok)return;
    const rows=await r.json();
    const count=Array.isArray(rows)?rows.length:0;
    badge.textContent=count;

    if(samaDriverStatusLastCount===null){
      samaDriverStatusLastCount=count;
      return;
    }
    if(count>samaDriverStatusLastCount){
      samaDriverStatusBeep();
      const btn=document.getElementById('samaDriverStatusOpsBtn');
      if(btn){
        const old=btn.style.boxShadow;
        btn.style.boxShadow='0 0 0 5px rgba(239,68,68,.35),0 0 22px rgba(239,68,68,.9)';
        setTimeout(()=>{btn.style.boxShadow=old||'';},1800);
      }
    }
    samaDriverStatusLastCount=count;
  }catch(_e){}
}

document.addEventListener('click',()=>{if(samaDriverStatusSoundEnabled)samaDriverStatusEnsureAudio();},{once:true});
setTimeout(samaInstallDriverStatusOperationsButton,500);
setInterval(()=>{samaInstallDriverStatusOperationsButton();samaRefreshDriverStatusOpsCount();},5000);
'''

# Insert into the application's existing JS block, before a stable function marker.
markers=['async function openEntry(scna){','function showPage(','async function loadDashboard(']
inserted=0
for marker in markers:
    if marker in html and 'samaInstallDriverStatusOperationsButton' not in html:
        html=html.replace(marker, helper+'\n'+marker,1)
        inserted=1
        break

# Last-resort insertion before the final existing </script>, still no extra script block.
if not inserted and 'samaInstallDriverStatusOperationsButton' not in html:
    pos=html.rfind('</script>')
    if pos!=-1:
        html=html[:pos]+helper+'\n'+html[pos:]
        inserted=1

core.HTML=html
print(f'[SAMA] Driver notifications Operations launcher V3 + sound toggle active: js_inserted={inserted}')
