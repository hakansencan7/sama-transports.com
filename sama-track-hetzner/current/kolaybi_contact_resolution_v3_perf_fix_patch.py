import kolaybi_contact_resolution_v3_patch as v3
import kolaybi_sync_patch as sync

app = v3.app
core = v3.core
kdb = v3.kdb


def _txt(v):
    return str(v or '').strip()


def _cache_assoc_shallow(row):
    """Cache list response only. Detail/address API is intentionally on-demand per SCNA."""
    if not isinstance(row, dict):
        return None
    cid = v3.base._rid(row)
    if not cid:
        return None
    display = v3._display(row)
    code = _txt(row.get('code') or row.get('associate_code') or row.get('contact_code'))
    plate = v3.base._plate(row)
    aid = v3.base._address_id(row)
    assoc_type = _txt(row.get('associate_type') or row.get('type') or row.get('contact_type'))
    c = kdb()
    try:
        old = c.execute('SELECT key FROM associates WHERE contact_id=? LIMIT 1',(cid,)).fetchone()
        if old:
            c.execute('''UPDATE associates SET name=?,full_name=?,plate=CASE WHEN ?<>'' THEN ? ELSE plate END,
                         address_id=CASE WHEN ?<>'' THEN ? ELSE address_id END,associate_type=?,source_code=?,
                         is_active=1,note='KolayBi API sync v3',updated_at=CURRENT_TIMESTAMP WHERE contact_id=?''',
                      (display,display,plate,plate,aid,aid,assoc_type,code,cid))
        else:
            key = (code or display or cid).upper()
            collision = c.execute('SELECT contact_id FROM associates WHERE UPPER(key)=UPPER(?) LIMIT 1',(key,)).fetchone()
            if collision and _txt(collision['contact_id']) != cid:
                key = key + '#' + cid
            c.execute('''INSERT INTO associates(key,name,full_name,plate,contact_id,address_id,associate_type,source_code,is_active,note,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,1,'KolayBi API sync v3',CURRENT_TIMESTAMP)''',
                      (key,display,display,plate,cid,aid,assoc_type,code))
        c.commit()
        got = c.execute('SELECT * FROM associates WHERE contact_id=? ORDER BY updated_at DESC LIMIT 1',(cid,)).fetchone()
        return dict(got) if got else None
    finally:
        c.close()


def _sync_associates_fast_v3():
    rows, errors = v3.base._paged('associates')
    c = kdb()
    try:
        # API-origin rows not returned anymore become inactive. Curated/manual rows stay intact.
        c.execute("UPDATE associates SET is_active=0 WHERE note LIKE 'KolayBi API%'")
        c.commit()
    finally:
        c.close()
    count = 0
    for row in rows:
        if not v3._active(row):
            continue
        if _cache_assoc_shallow(row):
            count += 1
    return count, errors[-8:]


def _purchase_contact_once(plate):
    contact, source, _ = v3._resolve_purchase(plate)
    return contact, source


def _sale_contact_once(customer):
    contact, source, _ = v3._resolve_sale(customer)
    return contact, source


sync._sync_associates = _sync_associates_fast_v3
v3._sync_associates_v3 = _sync_associates_fast_v3
v3.base._sync_associates_v2 = _sync_associates_fast_v3
v3.base._purchase_contact = _purchase_contact_once
v3.base._sale_contact = _sale_contact_once

print('[SAMA] KolayBi contact V3 performance fix active: bulk sync shallow, address detail on-demand only')
