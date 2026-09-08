import re
import kolaybi_complete_expenses_patch as base

app = base.app
core = base.core
kdb = base.kdb
html = core.HTML
webmod = base.webmod


def _norm(v):
    s = str(v or '').upper()
    s = s.replace('İ','I').replace('Ş','S').replace('Ğ','G').replace('Ü','U').replace('Ö','O').replace('Ç','C')
    return re.sub(r'[^A-Z0-9]+', '', s)


_original_preview = webmod.kolaybi_preview


def _preview_diagnostic(scna: str):
    pv = _original_preview(scna)

    # If the old strict lookup did not find a contact, try one SAFE normalized match.
    # We only accept exactly one candidate, never a random/fuzzy winner.
    if not pv.get('contact'):
        wanted_name = _norm(pv.get('customer'))
        wanted_plate = _norm(pv.get('plate'))
        c = kdb()
        try:
            rows = [dict(r) for r in c.execute('SELECT * FROM associates WHERE is_active=1').fetchall()]
        finally:
            c.close()
        candidates = []
        for r in rows:
            rn = _norm(r.get('name'))
            rk = _norm(r.get('key'))
            rp = _norm(r.get('plate'))
            if wanted_plate and rp and wanted_plate == rp:
                candidates.append(r)
                continue
            if wanted_name and (wanted_name == rn or wanted_name == rk):
                candidates.append(r)
        uniq = {}
        for r in candidates:
            cid = str(r.get('contact_id') or '').strip()
            if cid:
                uniq[cid] = r
        if len(uniq) == 1:
            pv['contact'] = next(iter(uniq.values()))

    missing = []
    missing_products = sorted(set(pv.get('missing_product_codes') or []))
    if missing_products:
        missing.append('PRODUCT ID: ' + ', '.join(missing_products))

    contact = pv.get('contact') or {}
    if not str(contact.get('contact_id') or '').strip():
        missing.append('CARİ / CONTACT ID')
    if not str(contact.get('address_id') or '').strip():
        missing.append('ADDRESS ID')

    project = pv.get('project') or {}
    if not str(project.get('project_id') or '').strip():
        missing.append('PROJECT ID')

    pv['missing_reasons'] = missing
    pv['ready'] = bool(pv.get('items')) and not missing
    return pv


webmod.kolaybi_preview = _preview_diagnostic
base.webmod.kolaybi_preview = _preview_diagnostic

for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/preview/{scna}' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _preview_diagnostic
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _preview_diagnostic
        break

# The send engine resolves preview through the patched web module, so it will now
# also require address_id before showing/sending a real KolayBi document.

# Improve preview UI: show Product ID on every item and exact missing reasons.
old = "state.innerHTML=x.ready?'<span class=\"kb-ready\">✓ GÖNDERİME HAZIR</span>':'<span class=\"kb-missing\">EKSİK EŞLEŞTİRME VAR</span>';"
new = "state.innerHTML=x.ready?'<span class=\"kb-ready\">✓ GÖNDERİME HAZIR</span>':'<span class=\"kb-missing\">EKSİK: '+kbEsc((x.missing_reasons||[]).join(' | ')||'EŞLEŞTİRME VAR')+'</span>';"
if old in html:
    html = html.replace(old, new, 1)

old_item = "<div class=\"kb-item\"><span><b>${kbEsc(i.name)}</b>${i.description?'<br><small>'+kbEsc(i.description)+'</small>':''}</span><span>${kbEsc(i.quantity)} × ${Number(i.unit_price||0).toLocaleString('tr-TR')} = <b>${Number(i.total||0).toLocaleString('tr-TR')}</b></span></div>"
new_item = "<div class=\"kb-item\"><span><b>${kbEsc(i.name)}</b><br><small>Product ID: ${kbEsc(i.product_id||'-')}</small>${i.description?'<br><small>'+kbEsc(i.description)+'</small>':''}</span><span>${kbEsc(i.quantity)} × ${Number(i.unit_price||0).toLocaleString('tr-TR')} = <b>${Number(i.total||0).toLocaleString('tr-TR')}</b></span></div>"
if old_item in html:
    html = html.replace(old_item, new_item, 1)

core.HTML = html
print('[SAMA] KolayBi preview diagnostics active: product/contact/address/project reasons + safe contact auto-match')
