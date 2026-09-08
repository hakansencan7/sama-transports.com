# Premium, isolated login visual for SAMA TRACK.
# The auth overlay becomes fully opaque so operational UI/content never shows
# behind the login form. CSS-only visuals keep the login fast and self-contained.

import edit_center_searchable_choices_patch as base

app = base.app
core = base.core
html = core.HTML

MARK = "SAMA_LOGIN_VISUAL_V1"
BACK_MARK = "SAMA_LOGIN_BACK_HOME_V1"

CSS = r'''
/* SAMA_LOGIN_VISUAL_V1 */
.auth-overlay{
  position:fixed;inset:0;z-index:200000;display:flex;align-items:center;justify-content:center;
  padding:20px;overflow:hidden;isolation:isolate;
  background:
    radial-gradient(circle at 18% 20%,rgba(14,165,233,.18),transparent 34%),
    radial-gradient(circle at 82% 72%,rgba(37,99,235,.20),transparent 38%),
    linear-gradient(135deg,#030812 0%,#071523 47%,#06101d 100%);
}
.auth-overlay::before{
  content:"";position:absolute;inset:-12%;z-index:-2;pointer-events:none;opacity:.9;
  background-image:
    linear-gradient(rgba(56,189,248,.055) 1px,transparent 1px),
    linear-gradient(90deg,rgba(56,189,248,.055) 1px,transparent 1px);
  background-size:48px 48px;
  transform:perspective(700px) rotateX(59deg) translateY(24%);
  transform-origin:center bottom;
  mask-image:linear-gradient(to bottom,transparent 2%,#000 38%,#000 100%);
}
.auth-overlay::after{
  content:"";position:absolute;width:76vw;height:76vw;max-width:980px;max-height:980px;
  left:50%;top:55%;transform:translate(-50%,-50%);z-index:-1;pointer-events:none;
  border:1px solid rgba(56,189,248,.12);border-radius:50%;
  box-shadow:0 0 0 90px rgba(56,189,248,.025),0 0 0 180px rgba(56,189,248,.018),0 0 120px rgba(14,165,233,.10);
  animation:samaLoginPulse 8s ease-in-out infinite;
}
@keyframes samaLoginPulse{0%,100%{opacity:.62;transform:translate(-50%,-50%) scale(.98)}50%{opacity:1;transform:translate(-50%,-50%) scale(1.025)}}
.auth-card{
  position:relative;width:min(430px,95vw);padding:30px 28px 27px;border-radius:22px;
  color:#eaf5ff;background:linear-gradient(150deg,rgba(13,30,49,.94),rgba(8,20,35,.90));
  border:1px solid rgba(125,211,252,.18);
  box-shadow:0 35px 90px rgba(0,0,0,.56),inset 0 1px 0 rgba(255,255,255,.08);
  backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);
}
.auth-card::before{
  content:"SECURE OPERATIONS";display:block;margin-bottom:15px;color:#7dd3fc;
  font-size:10px;font-weight:900;letter-spacing:2.5px;text-align:center;
}
.auth-logo{text-align:center;font-weight:950;font-size:30px;letter-spacing:.8px;margin-bottom:22px;color:#f8fbff}
.auth-logo span{color:#38bdf8;text-shadow:0 0 22px rgba(56,189,248,.35)}
.auth-card h3{text-align:center;margin:0 0 20px;color:#fff;font-size:17px}
.auth-card .field{gap:7px;margin-bottom:14px}
.auth-card .field label{color:#9fb3c8;font-size:11px;letter-spacing:.35px}
.auth-card input{
  width:100%;height:46px;border-radius:11px;border:1px solid rgba(148,163,184,.22)!important;
  background:rgba(2,10,19,.55)!important;color:#f8fafc!important;outline:none;
  box-shadow:inset 0 1px 8px rgba(0,0,0,.17);
}
.auth-card input:focus{border-color:#38bdf8!important;box-shadow:0 0 0 3px rgba(56,189,248,.12)}
.auth-card .btn.primary{
  height:46px;margin-top:7px;border-radius:11px;background:linear-gradient(135deg,#0284c7,#2563eb)!important;
  box-shadow:0 12px 28px rgba(37,99,235,.28);transition:transform .16s ease,filter .16s ease;
}
.auth-card .btn.primary:hover{transform:translateY(-1px);filter:brightness(1.08)}
.auth-card .small{color:#fca5a5!important;text-align:center}
#samaBackToMain{
  display:flex;align-items:center;justify-content:center;gap:8px;width:100%;height:42px;
  margin-top:12px;border:1px solid rgba(148,163,184,.20);border-radius:11px;
  text-decoration:none;color:#cbd5e1;background:rgba(255,255,255,.035);
  font-size:12px;font-weight:800;letter-spacing:.2px;transition:.16s ease;
}
#samaBackToMain:hover{color:#fff;border-color:rgba(125,211,252,.38);background:rgba(56,189,248,.08);transform:translateY(-1px)}
#samaBackToMain .sama-back-arrow{font-size:16px;color:#7dd3fc}
.auth-overlay:has(#authLoginBox)::before{animation:samaGridDrift 18s linear infinite}
@keyframes samaGridDrift{from{background-position:0 0,0 0}to{background-position:48px 48px,48px 48px}}
#samaLangBox{z-index:200100!important}
@media(max-width:600px){
  .auth-overlay{padding:14px}.auth-card{padding:25px 20px;border-radius:18px}
  .auth-logo{font-size:26px}.auth-overlay::after{width:120vw;height:120vw}
}
'''

if MARK not in html:
    style_block = "<style>\n" + CSS + "\n</style>\n"
    if "</head>" in html:
        html = html.replace("</head>", style_block + "</head>", 1)
    else:
        print("[SAMA] Login visual skipped safely: </head> not found")

if BACK_MARK not in html:
    back_html = r'''<!-- SAMA_LOGIN_BACK_HOME_V1 -->
<a id="samaBackToMain" href="https://www.sama-transports.com/" aria-label="Ana Siteye Dön">
  <span class="sama-back-arrow" aria-hidden="true">←</span>
  <span id="samaBackToMainText">Ana Siteye Dön</span>
</a>
<script>
(function(){
  const labels={tr:'Ana Siteye Dön',en:'Back to Main Website',ar:'العودة إلى الموقع الرئيسي'};
  function updateSamaBackHome(){
    const el=document.getElementById('samaBackToMainText');
    if(!el)return;
    const l=(document.documentElement.lang||localStorage.getItem('sama_lang')||'tr').toLowerCase();
    el.textContent=labels[l]||labels.tr;
    const a=document.getElementById('samaBackToMain');
    if(a)a.setAttribute('aria-label',el.textContent);
  }
  document.addEventListener('DOMContentLoaded',updateSamaBackHome);
  new MutationObserver(updateSamaBackHome).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
  updateSamaBackHome();
})();
</script>'''
    anchor = '    <div id="authMsg" class="small" style="margin-top:10px"></div>'
    if anchor in html:
        html = html.replace(anchor, anchor + "\n" + back_html, 1)
    else:
        print("[SAMA] Login back-home button skipped safely: authMsg anchor not found")

core.HTML = html
print("[SAMA] Premium isolated login visual + main website return active")
