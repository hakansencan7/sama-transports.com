from fastapi import HTTPException, Request

import app as core

app = core.app

# SAMA_SECTION_PERMISSIONS_V1
# Fill permission gaps left by modules that were added after the original auth
# system. Backend checks are authoritative; the UI mirrors the same matrix.
NEW_PERMISSION_LABELS = {
    "finance.view": "Finans / Kârlılık Gör",
    "advances.view": "Avans / Kişi Hesapları Gör",
    "advances.edit": "Avans / Kişi Hesapları Ekle-Düzenle",
    "cash.view": "Günlük Kasa Gör",
    "cash.edit": "Günlük Kasa Ekle-Düzenle",
    "kolaybi.view": "KolayBi Gör",
    "kolaybi.edit": "KolayBi Ayar / Eşleştirme Düzenle",
    "kolaybi.send": "KolayBi Fatura Gönder",
}

core.PERMISSION_LABELS.update(NEW_PERMISSION_LABELS)

# cash.expense.edit was a narrow compatibility permission from before Daily Cash
# had a complete view/edit pair. Continue accepting it internally without showing
# two cash-edit boxes in Admin > Permissions.
core.PERMISSION_LABELS.pop("cash.expense.edit", None)

# ADMIN always owns every current permission loaded here.
core.ROLE_DEFAULTS.setdefault("ADMIN", set()).update(NEW_PERMISSION_LABELS)

# Preserve existing normal-role behavior where those pages were already available.
# Avans and KolayBi remain explicit grants for non-admin users.
core.ROLE_DEFAULTS.setdefault("OPERATOR", set()).update({
    "finance.view", "cash.view", "cash.edit"
})
core.ROLE_DEFAULTS.setdefault("VIEWER", set()).update({
    "finance.view", "cash.view"
})


# Effective permission compatibility + dependency rules.
_original_user_permissions = core._user_permissions


def _section_user_permissions(c, user_id: int, role: str):
    perms = set(_original_user_permissions(c, user_id, role))
    try:
        overrides = {
            str(r["permission"]): int(r["allowed"] or 0)
            for r in c.execute(
                "SELECT permission,allowed FROM auth_user_permissions WHERE user_id=?",
                (user_id,),
            ).fetchall()
        }
    except Exception:
        overrides = {}

    # Legacy report.view users keep Finance unless Admin explicitly changes the new
    # Finance checkbox for that user.
    if "finance.view" not in overrides and "report.view" in perms:
        perms.add("finance.view")

    # Before this patch Avans was exposed through users.manage. Preserve that for
    # existing customized accounts unless Admin explicitly sets the new Avans boxes.
    if "users.manage" in perms:
        if "advances.view" not in overrides:
            perms.add("advances.view")
        if "advances.edit" not in overrides:
            perms.add("advances.edit")

    # Legacy Daily Cash edit permission migrates transparently.
    if "cash.expense.edit" in perms:
        perms.update({"cash.view", "cash.edit"})
    if "cash.edit" in perms:
        perms.update({"cash.view", "cash.expense.edit"})

    # Edit/send permissions necessarily include viewing the section.
    if "advances.edit" in perms:
        perms.add("advances.view")
    if "kolaybi.edit" in perms or "kolaybi.send" in perms:
        perms.add("kolaybi.view")

    if str(role or "").upper() == "ADMIN":
        perms.update(core.PERMISSION_LABELS.keys())
        perms.add("cash.expense.edit")

    return perms


core._user_permissions = _section_user_permissions


# Central backend mapping. These rules run before the older generic mapper so a
# section-specific permission cannot fall back to a broad permission or to mere
# authentication.
_previous_required_permission = core._required_permission


def _section_required_permission(path: str, method: str):
    p = str(path or "")
    m = str(method or "GET").upper()

    # KOLAYBI: viewing, configuration/mapping and real invoice sending are separate.
    if p.startswith("/api/kolaybi/") or p == "/api/kolaybi":
        if "/send" in p or p.endswith("/send"):
            return "kolaybi.send"
        # This endpoint is POST only because it accepts pasted input; it reads the
        # local audit snapshot and does not mutate KolayBi/SAMA accounting data.
        if p == "/api/kolaybi/accounting-audit/check":
            return "kolaybi.view"
        return "kolaybi.view" if m == "GET" else "kolaybi.edit"

    # ACCOUNTING / FINANCE sections.
    if p.startswith("/api/advances"):
        return "advances.view" if m == "GET" else "advances.edit"
    if p.startswith("/api/cash-control"):
        return "cash.view" if m == "GET" else "cash.edit"
    if p.startswith("/api/finance"):
        return "finance.view"

    # Section endpoints that predate the original permission-prefix map.
    if p.startswith("/api/scna-detail/"):
        return "shipment.view"
    if p.startswith("/api/vehicle-card/"):
        return "fleet.view"
    if p.startswith("/api/driver-card/"):
        return "driver.view"
    if p.startswith("/api/trips-deleted"):
        return "shipment.delete"
    if p.startswith("/api/cash-diagnostic/") or p.startswith("/api/cash-out-diagnostic/"):
        return "shipment.view"
    if p.startswith("/api/entry-expense-memory"):
        return "shipment.view"
    if p.startswith("/api/entry-expense-labels/"):
        return "shipment.view" if m == "GET" else "shipment.edit"
    if p.startswith("/api/print-"):
        return "shipment.view"
    if p.startswith("/api/fleet/gps-state"):
        return "operation.edit"

    return _previous_required_permission(path, method)


core._required_permission = _section_required_permission


# Some older functions performed a second local users.manage/cash guard because
# their section did not yet have its own permission. Translate only those section
# checks; Users & Permissions itself remains users.manage.
_original_require_user_perm = core._require_user_perm


def _section_require_user_perm(request: Request, perm: str):
    path = str(getattr(getattr(request, "url", None), "path", "") or "")
    user = core._request_user(request)
    if not user:
        raise HTTPException(401, "Oturum gerekli.")
    role = str(user.get("role") or "").upper()
    perms = set(user.get("permissions") or [])

    if path.startswith("/api/advances") and perm == "users.manage":
        if role == "ADMIN" or "advances.edit" in perms:
            return user
        raise HTTPException(403, "Avans / Kişi Hesapları düzenleme yetkiniz yok.")

    if path.startswith("/api/cash-control") and perm == "cash.expense.edit":
        if role == "ADMIN" or "cash.edit" in perms or "cash.expense.edit" in perms:
            return user
        raise HTTPException(403, "Günlük Kasa düzenleme yetkiniz yok.")

    return _original_require_user_perm(request, perm)


core._require_user_perm = _section_require_user_perm


# KolayBi used to contain a second ADMIN-role-only lock. Point that common guard
# at the new permission matrix. Middleware still distinguishes edit vs send by URL,
# so an edit-only user cannot send invoices and a send-only user cannot edit setup.
try:
    import kolaybi_web_module_patch as kb_web

    def _kolaybi_permission_guard():
        user = core.CURRENT_AUTH_USER.get() or {}
        role = str(user.get("role") or "").upper()
        perms = set(user.get("permissions") or [])
        if role == "ADMIN" or perms.intersection({"kolaybi.edit", "kolaybi.send"}):
            return user
        raise HTTPException(
            status_code=403,
            detail="Bu KolayBi işlemi için yetkiniz yok.",
        )

    kb_web._admin_required = _kolaybi_permission_guard
except Exception as exc:
    print("[SAMA] KolayBi permission guard warning:", exc)


# UI mirror. Backend rules above remain the security boundary. The UI hides pages
# and actions the user cannot use and also blocks direct show('panel') calls.
_ui = r'''
<script>/* SAMA_SECTION_PERMISSIONS_V1 */
(function(){
  const PANEL_PERMS={
    dash:'dashboard.view',
    trips:'shipment.view',
    exit:'shipment.edit',
    entry:'shipment.edit',
    detail:'shipment.view',
    editcenter:'shipment.edit',
    quality:'shipment.view',
    compare:'excel.import',
    bulkfix:'shipment.edit',
    opcenter:'operation.view',
    liveops:'operation.view',
    loadqueue:'operation.view',
    vesselops:'operation.view',
    maintops:'maintenance.view',
    routes:'operation.view',
    fleetmanage:'fleet.view',
    vehiclecard:'fleet.view',
    maintenance:'maintenance.view',
    drivermanage:'driver.view',
    drivercard:'driver.view',
    anomaly:'report.view',
    daily:'report.view',
    performance:'report.view',
    finance:'finance.view',
    alerts:'report.view',
    audit:'audit.view',
    advances:'advances.view',
    cashcontrol:'cash.view',
    kolaybi:'kolaybi.view',
    useradmin:'users.manage',
    deleted:'shipment.delete'
  };

  function currentUserReady(){
    try{return typeof AUTH_USER!=='undefined' && !!AUTH_USER;}
    catch(_e){return false;}
  }

  function allowed(perm){
    try{return !perm || (typeof hasPerm==='function' && hasPerm(perm));}
    catch(_e){return false;}
  }

  function setActionDisplay(el,ok){
    if(!el)return;
    if(ok){
      if(el.dataset.samaPermHidden==='1'){
        el.style.display='';
        delete el.dataset.samaPermHidden;
      }
    }else{
      el.style.display='none';
      el.dataset.samaPermHidden='1';
    }
  }

  function applyKolayBiActions(){
    const panel=document.getElementById('kolaybi');
    if(!panel)return;
    const canEdit=allowed('kolaybi.edit'), canSend=allowed('kolaybi.send');
    panel.querySelectorAll('button').forEach(btn=>{
      const oc=String(btn.getAttribute('onclick')||'');
      const txt=String(btn.innerText||'').toLocaleUpperCase('tr-TR');
      const sendAction=/send/i.test(oc)||txt.includes('GÖNDER');
      const editAction=/kb(Save|Sync|Create|Delete|Refresh|Auto|Map|Select|Clear|TestConnection|Tag)/i.test(oc)
        || txt.includes('KAYDET') || txt.includes('OLUŞTUR') || txt.includes('SİL')
        || txt.includes('YENİLE') || txt.includes('ÇEK') || txt.includes('EŞLEŞTİR');
      if(sendAction)setActionDisplay(btn,canSend);
      else if(editAction)setActionDisplay(btn,canEdit);
    });
  }

  function applySectionPermissions(){
    if(!currentUserReady())return;

    // This map is authoritative for navigation. Re-show an allowed item even if
    // the older applyAuthUI() hid it using a legacy permission (notably Avans).
    document.querySelectorAll('.nav button[onclick*="show("]').forEach(btn=>{
      const m=String(btn.getAttribute('onclick')||'').match(/show\('([^']+)'/);
      if(!m)return;
      const perm=PANEL_PERMS[m[1]];
      if(perm)btn.style.display=allowed(perm)?'':'none';
    });

    // The management group contains both Users and Deleted Trips, so decide group
    // visibility from its child buttons rather than users.manage alone.
    document.querySelectorAll('.nav-group').forEach(group=>{
      const buttons=[...group.querySelectorAll('.nav-group-items > button')];
      if(!buttons.length)return;
      const anyVisible=buttons.some(b=>getComputedStyle(b).display!=='none');
      group.style.display=anyVisible?'':'none';
    });

    applyKolayBiActions();
  }

  const oldApply=window.applyAuthUI;
  if(typeof oldApply==='function'){
    window.applyAuthUI=function(){
      const r=oldApply.apply(this,arguments);
      setTimeout(applySectionPermissions,0);
      return r;
    };
  }

  const oldShow=window.show;
  if(typeof oldShow==='function'){
    window.show=function(id,btn){
      const perm=PANEL_PERMS[id];
      if(perm&&!allowed(perm)){
        alert('Bu bölümü görüntüleme yetkiniz yok.');
        return;
      }
      return oldShow.apply(this,arguments);
    };
  }

  // KolayBi and some accounting controls are injected dynamically by later
  // patches, so re-apply action visibility as their DOM changes.
  let timer=null;
  const boot=()=>{
    clearTimeout(timer);
    timer=setTimeout(applySectionPermissions,30);
  };
  document.addEventListener('DOMContentLoaded',boot);
  if(document.body){
    new MutationObserver(boot).observe(document.body,{childList:true,subtree:true});
  }else{
    document.addEventListener('DOMContentLoaded',()=>new MutationObserver(boot).observe(document.body,{childList:true,subtree:true}),{once:true});
  }
})();
</script>
'''

if "SAMA_SECTION_PERMISSIONS_V1" not in core.HTML:
    if "</body>" in core.HTML:
        # Insert before the real page-closing body tag. Earlier print/report
        # templates contain literal </body> strings inside JavaScript; replacing
        # the first occurrence corrupts that script and can break login/UI boot.
        head, body_close, tail = core.HTML.rpartition("</body>")
        core.HTML = head + _ui + "\n" + body_close + tail
    else:
        core.HTML += _ui

print("[SAMA] Section permission matrix active: Finance, Advances, Daily Cash, KolayBi + existing sections")
