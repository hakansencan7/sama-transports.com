import re
from fastapi import HTTPException

import kolaybi_workflow_v2_patch as base
import kolaybi_sync_patch as sync

app = base.app
core = base.core
kdb = base.kdb
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _norm(v):
    s = _txt(v).upper()
    s = s.replace('İ','I').replace('Ş','S').replace('Ğ','G').replace('Ü','U').replace('Ö','O').replace('Ç','C')
    return re.sub(r'[^A-Z0-9]+', '', s)


def _words(v):
    s = _txt(v).upper()
    s = s.replace('İ','I').replace('Ş','S').replace('Ğ','G').replace('Ü','U').replace('Ö','O').replace('Ç','C')
    return [x for x in re.split(r'[^A-Z0-9]+', s) if x]


def _active(row):
    if not isinstance(row, dict):
        return True
    for key in ('is_active','active','enabled'):
        if key in row:
            v = row.get(key)
            if isinstance(v, bool):
                return v
            if str(v).strip().lower() in ('0','false','no','inactive','passive','pasif','disabled'):
                return False
    status = _txt(row.get('status')).lower()
    if status in ('inactive','passive','pasif','disabled','deleted','closed'):
        return False
    return True


def _display(row):
    return base._display_assoc(row) if isinstance(row, dict) else ''


def _detail(contact_id):
    cid = _txt(contact_id)
    if not cid:
        return None
    for path in (f'associates/{cid}', f'associate/{cid}'):
        try:
            resp = sync._get(path, {})
            if isinstance(resp, dict):
                data = resp.get('data')
                if isinstance(data, dict):
                    return data
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    return data[0]
                return resp
        except Exception:
            continue
    return None


def _cache_live_assoc(row):
    if not isinstance(row, dict):
        return None
    cid = base._rid(row)
    if not cid:
        return None
    detail = _detail(cid)
    merged = dict(row)
    if isinstance(detail, dict):
        # Detail is authoritative for address/full name but list values remain fallback.
        merged.update({k:v for k,v in detail.items() if v not in (None,'',[],{})})
    display = _display(merged) or _display(row)
    code = _txt(merged.get('code') or merged.get('associate_code') or merged.get('contact_code'))
    plate = base._plate(merged) or base._plate(row)
    aid = base._address_id(merged) or base._address_id(row)
    assoc_type = _txt(merged.get('associate_type') or merged.get('type') or merged.get('contact_type'))
    c = kdb()
    try:
        old = c.execute('SELECT key FROM associates WHERE contact_id=? LIMIT 1',(cid,)).fetchone()
        if old:
            c.execute('''UPDATE associates SET name=?,full_name=?,plate=CASE WHEN ?<>'' THEN ? ELSE plate END,
                         address_id=CASE WHEN ?<>'' THEN ? ELSE address_id END,associate_type=?,source_code=?,
                         is_active=1,note='KolayBi API live resolve',updated_at=CURRENT_TIMESTAMP WHERE contact_id=?''',
                      (display,display,plate,plate,aid,aid,assoc_type,code,cid))
            key = _txt(old['key'])
        else:
            key = (code or display or cid).upper()
            collision = c.execute('SELECT contact_id FROM associates WHERE UPPER(key)=UPPER(?) LIMIT 1',(key,)).fetchone()
            if collision and _txt(collision['contact_id']) != cid:
                key = key + '#' + cid
            c.execute('''INSERT INTO associates(key,name,full_name,plate,contact_id,address_id,associate_type,source_code,is_active,note,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,1,'KolayBi API live resolve',CURRENT_TIMESTAMP)''',
                      (key,display,display,plate,cid,aid,assoc_type,code))
        c.commit()
        got = c.execute('SELECT * FROM associates WHERE contact_id=? ORDER BY updated_at DESC LIMIT 1',(cid,)).fetchone()
        return dict(got) if got else None
    finally:
        c.close()


def _local_rows():
    c = kdb()
    try:
        return [dict(r) for r in c.execute("SELECT * FROM associates WHERE is_active=1 AND contact_id<>''").fetchall()]
    finally:
        c.close()


def _live_search(term):
    wanted = _norm(term)
    if not wanted:
        return []
    found = {}
    params_list = (
        {'name':term,'per_page':100},
        {'title':term,'per_page':100},
        {'q':term,'per_page':100},
        {'search':term,'per_page':100},
    )
    for params in params_list:
        try:
            rows = sync._rows(sync._get('associates', params))
        except Exception:
            continue
        for row in rows:
            cid = base._rid(row)
            if not cid or not _active(row):
                continue
            fields = [
                _display(row), row.get('name'), row.get('title'), row.get('company_name'),
                row.get('associate_name'), row.get('full_name'), row.get('code'),
                row.get('associate_code'), row.get('contact_code'), row.get('surname')
            ]
            combined = ' '.join(_txt(x) for x in fields if _txt(x))
            if wanted in {_norm(x) for x in fields if _txt(x)} or all(w in _words(combined) for w in _words(term)):
                found[cid] = row
    return list(found.values())


def _enrich_cached(row):
    if not row:
        return None
    if _txt(row.get('address_id')):
        return row
    cid = _txt(row.get('contact_id'))
    d = _detail(cid)
    if not d:
        return row
    merged = dict(row)
    aid = base._address_id(d)
    if aid:
        merged['address_id'] = aid
    display = _display(d)
    if display:
        merged['name'] = display
        merged['full_name'] = display
    c = kdb()
    try:
        c.execute('''UPDATE associates SET name=CASE WHEN ?<>'' THEN ? ELSE name END,
                     full_name=CASE WHEN ?<>'' THEN ? ELSE full_name END,
                     address_id=CASE WHEN ?<>'' THEN ? ELSE address_id END,
                     updated_at=CURRENT_TIMESTAMP WHERE contact_id=?''',
                  (display,display,display,display,aid,aid,cid))
        c.commit()
    finally:
        c.close()
    return merged


def _candidate_label(rows):
    out=[]
    for row in rows[:4]:
        out.append((_display(row) or _txt(row.get('key')) or '?')+' #'+_txt(row.get('contact_id')))
    return '; '.join(out)


def _purchase_candidates(plate, rows):
    target = _norm(plate)
    freight = _norm('FREIGHT '+_txt(plate))
    scored = {}
    for row in rows:
        cid = _txt(row.get('contact_id'))
        if not cid:
            continue
        vals = [_norm(row.get('plate')),_norm(row.get('name')),_norm(row.get('full_name')),_norm(row.get('key')),_norm(row.get('source_code'))]
        if not any(target and target in v for v in vals if v):
            continue
        score = 0
        if freight in vals:
            score += 220
        if _norm(row.get('plate')) == target:
            score += 120
        if any(v.startswith('FREIGHT') and target in v for v in vals if v):
            score += 80
        note = _txt(row.get('note'))
        if note and not note.startswith('KolayBi API'):
            score += 50  # manual/curated row has priority, same as old CARILER logic
        if _txt(row.get('address_id')):
            score += 20
        if _active(row):
            score += 5
        prev = scored.get(cid)
        if not prev or score > prev[0]:
            scored[cid] = (score,row)
    return sorted(scored.values(), key=lambda x:(x[0],_txt(x[1].get('updated_at'))), reverse=True)


def _resolve_purchase(plate):
    ranked = _purchase_candidates(plate,_local_rows())
    if ranked and (len(ranked)==1 or ranked[0][0] > ranked[1][0]):
        return _enrich_cached(ranked[0][1]), 'PLATE/FREIGHT SCORE', [x[1] for x in ranked]

    # Old working program also tried FREIGHT {PLATE} against the API/cache. Do the same on ambiguity.
    live = _live_search('FREIGHT '+_txt(plate))
    cached = [x for x in (_cache_live_assoc(r) for r in live) if x]
    ranked_live = _purchase_candidates(plate,cached or _local_rows())
    if ranked_live and (len(ranked_live)==1 or ranked_live[0][0] > ranked_live[1][0]):
        return _enrich_cached(ranked_live[0][1]), 'LIVE FREIGHT/PLATE', [x[1] for x in ranked_live]
    candidates = [x[1] for x in (ranked_live or ranked)]
    return None, ('AMBIGUOUS ['+_candidate_label(candidates)+']') if candidates else 'NOT FOUND', candidates


def _sale_candidates(customer, rows):
    wanted = _norm(customer)
    wanted_words = _words(customer)
    scored = {}
    for row in rows:
        cid = _txt(row.get('contact_id'))
        if not cid:
            continue
        display = _display(row)
        vals = [display,row.get('name'),row.get('full_name'),row.get('key'),row.get('source_code')]
        norms = {_norm(x) for x in vals if _txt(x)}
        combined = ' '.join(_txt(x) for x in vals if _txt(x))
        word_match = bool(wanted_words) and all(w in _words(combined) for w in wanted_words)
        if wanted not in norms and not word_match:
            continue
        score = 200 if wanted in norms else 100
        note = _txt(row.get('note'))
        if note and not note.startswith('KolayBi API'):
            score += 30
        if _txt(row.get('address_id')):
            score += 20
        if _active(row):
            score += 5
        prev = scored.get(cid)
        if not prev or score > prev[0]:
            scored[cid] = (score,row)
    return sorted(scored.values(), key=lambda x:(x[0],_txt(x[1].get('updated_at'))), reverse=True)


def _resolve_sale(customer):
    ranked = _sale_candidates(customer,_local_rows())
    if ranked and (len(ranked)==1 or ranked[0][0] > ranked[1][0]):
        return _enrich_cached(ranked[0][1]), 'CUSTOMER CACHE', [x[1] for x in ranked]

    live = _live_search(customer)
    cached = [x for x in (_cache_live_assoc(r) for r in live) if x]
    ranked_live = _sale_candidates(customer,cached or _local_rows())
    if ranked_live and (len(ranked_live)==1 or ranked_live[0][0] > ranked_live[1][0]):
        return _enrich_cached(ranked_live[0][1]), 'CUSTOMER LIVE API', [x[1] for x in ranked_live]
    candidates = [x[1] for x in (ranked_live or ranked)]
    return None, ('AMBIGUOUS ['+_candidate_label(candidates)+']') if candidates else 'NOT FOUND', candidates


def _sync_associates_v3():
    rows, errors = base._paged('associates')
    c = kdb()
    count = 0
    try:
        # Do not keep stale API rows active forever. Manual rows are deliberately untouched.
        c.execute("UPDATE associates SET is_active=0 WHERE note LIKE 'KolayBi API%'")
        c.commit()
    finally:
        c.close()
    for row in rows:
        if not _active(row):
            continue
        if _cache_live_assoc(row):
            count += 1
    return count, errors[-8:]


# The existing sync buttons look these globals up at click time.
sync._sync_associates = _sync_associates_v3
base._sync_associates_v2 = _sync_associates_v3


def _purchase_preview_v3(scna, trip=None):
    trip = trip or base._trip(scna)
    purchase = base.ui.base.webmod.kolaybi_preview(scna)
    contact, source, candidates = _resolve_purchase(trip.get('plate'))
    purchase['contact'] = contact
    purchase['contact_source'] = source
    purchase['contact_candidates'] = [{'name':_display(x),'contact_id':_txt(x.get('contact_id')),'address_id':_txt(x.get('address_id'))} for x in candidates[:6]]
    purchase['customer'] = _txt(trip.get('customer_name'))
    purchase['plate'] = _txt(trip.get('plate'))
    purchase['scna'] = _txt(scna)
    missing_products = sorted({_txt(x.get('code')) for x in purchase.get('items',[]) if not _txt(x.get('product_id'))})
    missing=[]
    if missing_products:
        missing.append('PRODUCT ID: '+', '.join(missing_products))
    if not contact:
        missing.append('PURCHASE CARİ: FREIGHT '+_txt(trip.get('plate')))
    elif not _txt(contact.get('contact_id')):
        missing.append('PURCHASE CONTACT ID')
    if contact and not _txt(contact.get('address_id')):
        missing.append('PURCHASE ADDRESS ID')
    project = purchase.get('project') or {}
    if not _txt(project.get('project_id')):
        missing.append('PROJECT ID')
    purchase['missing_product_codes'] = missing_products
    purchase['missing_reasons'] = missing
    purchase['total'] = sum(base._num(x.get('total')) for x in purchase.get('items',[]))
    purchase['ready'] = bool(purchase.get('items')) and not missing
    return purchase


def _sale_preview_v3(scna, trip=None, purchase=None):
    trip = trip or base._trip(scna)
    purchase = purchase or _purchase_preview_v3(scna,trip)
    customer = _txt(trip.get('customer_name'))
    contact, source, candidates = _resolve_sale(customer)
    # Let V2 resolve the route/product/amount, then replace only the contact logic and semantic unit.
    sale = base._sale_preview_original_for_v3(scna,trip,purchase) if hasattr(base,'_sale_preview_original_for_v3') else None
    if sale is None:
        # Temporarily use the original implementation stored below.
        sale = _ORIGINAL_SALE_PREVIEW(scna,trip,purchase)
    sale['contact'] = contact
    sale['contact_source'] = source
    sale['contact_candidates'] = [{'name':_display(x),'contact_id':_txt(x.get('contact_id')),'address_id':_txt(x.get('address_id'))} for x in candidates[:6]]
    # Shipment freight basis is authoritative. A KolayBi product card may say UNIT.EACH, but 35,040 kg is not 35,040 trucks.
    basis = _txt(sale.get('basis') or trip.get('freight_basis') or 'KG').upper()
    sale['unit'] = 'KG' if basis == 'KG' else 'ADET'
    missing = [x for x in (sale.get('missing_reasons') or []) if not x.startswith('SALE CARİ:') and x not in ('SALE CONTACT ID','SALE ADDRESS ID')]
    if not contact:
        missing.insert(0,'SALE CARİ: '+(customer or '-'))
    elif not _txt(contact.get('contact_id')):
        missing.insert(0,'SALE CONTACT ID')
    if contact and not _txt(contact.get('address_id')):
        missing.insert(0,'SALE ADDRESS ID')
    sale['missing_reasons'] = missing
    sale['ready'] = not missing
    return sale


_ORIGINAL_SALE_PREVIEW = base._sale_preview
base._sale_preview_original_for_v3 = _ORIGINAL_SALE_PREVIEW
base._purchase_contact = lambda plate: (_resolve_purchase(plate)[0], _resolve_purchase(plate)[1])
base._sale_contact = lambda customer: (_resolve_sale(customer)[0], _resolve_sale(customer)[1])
base._purchase_preview = _purchase_preview_v3
base._sale_preview = _sale_preview_v3

# The V2 route/send functions use module globals, so the replacements above also govern real sends.
# Improve the screen wording without creating another script block.
html = core.HTML
html = html.replace('QTY</th><th>RATE</th><th>SALE TOTAL</th><th>COLLECTION</th>', 'QTY / UNIT</th><th>RATE</th><th>SALE TOTAL</th><th>COLLECTION</th>', 1)
core.HTML = html

print('[SAMA] KolayBi contact resolution V3 active: stale API cleanup + plate scoring + live customer lookup + address detail + KG/ADET semantic unit')
