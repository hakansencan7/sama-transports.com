import re
from fastapi import HTTPException

import kolaybi_sale_cari_workflow_patch as sale_cari

app = sale_cari.app
core = sale_cari.core
workflow = sale_cari.workflow
v3 = sale_cari.v3
sync = sale_cari.sync


def _txt(v):
    return str(v or '').strip()


def _tax_value(obj):
    if not isinstance(obj, dict):
        return ''
    for key in ('tax_office','taxOffice','tax_office_name','tax_department','taxDepartment','vergi_dairesi'):
        val = obj.get(key)
        if isinstance(val, dict):
            val = val.get('name') or val.get('title') or val.get('value')
        if _txt(val):
            return _txt(val)
    data = obj.get('data')
    if isinstance(data, dict):
        return _tax_value(data)
    return ''


def _identity(name):
    source = _txt(name)
    digits = ''.join(ch for ch in source if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    total = sum((i + 1) * ord(ch) for i, ch in enumerate(source))
    suffix = str(total % 100000).zfill(5)
    return (digits + suffix + '0000000000')[:10]


def _request(method, path, payload):
    token = sync._token()
    r = sync.SESSION.request(
        method,
        f'{sync.BASE_URL}/{path.lstrip("/")}',
        headers={'Authorization': f'Bearer {token}', 'Channel': sync.CHANNEL},
        data=payload,
        timeout=35,
    )
    if not r.ok:
        raise RuntimeError(f'{method} /{path} HTTP {r.status_code}: {(r.text or "")[:500]}')
    try:
        return r.json()
    except Exception:
        return {'success': True, 'raw_text': r.text}


def _ensure_tax_office(contact_id, contact_name):
    cid = _txt(contact_id)
    name = _txt(contact_name)
    if not cid:
        raise HTTPException(status_code=400, detail='SALE Contact ID boş; vergi dairesi kontrol edilemez.')

    detail = v3._detail(cid)
    existing = _tax_value(detail)
    if existing:
        return existing, 'MEVCUT'

    surname = 'Freight'
    associate_type = 'customer'
    identity_no = ''
    if isinstance(detail, dict):
        surname = _txt(detail.get('surname')) or surname
        associate_type = _txt(detail.get('associate_type') or detail.get('type')) or associate_type
        identity_no = _txt(detail.get('identity_no') or detail.get('tax_number') or detail.get('identity_number'))
        name = name or _txt(detail.get('name') or detail.get('full_name') or detail.get('code'))
    identity_no = identity_no or _identity(name)

    base = {
        'name': name or f'CUSTOMER {cid}',
        'surname': surname,
        'identity_no': identity_no,
        'associate_type': associate_type,
        'is_corporate': 'true',
        'code': name or f'CUSTOMER {cid}',
    }

    tax_values = ('FATİH','FATIH','KADIKÖY','KADIKOY','BEYOĞLU','BEYOGLU','ŞİŞLİ','SISLI','BAKIRKÖY','BAKIRKOY')
    key_names = ('tax_office','tax_office_name','tax_department','vergi_dairesi','taxOffice')
    methods_paths = (
        ('PUT', f'associates/{cid}'),
        ('PATCH', f'associates/{cid}'),
        ('POST', f'associates/{cid}'),
        ('POST', f'associates/update/{cid}'),
        ('POST', f'associate/{cid}'),
        ('PUT', f'associate/{cid}'),
    )

    attempts = []
    for tax in tax_values:
        for key in key_names:
            payload = dict(base)
            payload[key] = tax
            for method, path in methods_paths:
                try:
                    resp = _request(method, path, payload)
                    after = v3._detail(cid)
                    got = _tax_value(after)
                    if got or (isinstance(resp, dict) and resp.get('success') is True):
                        return got or tax, f'{method} /{path}'
                except Exception as e:
                    attempts.append(str(e))
    raise HTTPException(
        status_code=502,
        detail='SALE cari vergi dairesi tamamlanamadı: ' + (name or cid) + ' | ' + ' | '.join(attempts[-5:])
    )


_old_sale_send = None
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/transaction/{scna}/sale/send' and 'POST' in (getattr(route, 'methods', set()) or set()):
        _old_sale_send = route.endpoint
        break


def kb_sale_send_with_tax_guard(scna: str):
    trip = workflow._trip(scna)
    purchase = workflow._purchase_preview(scna, trip)
    sale = workflow._sale_preview(scna, trip, purchase)
    contact = sale.get('contact') or {}
    if not _txt(contact.get('contact_id')):
        raise HTTPException(status_code=400, detail='SALE cari seçilmeden fatura gönderilemez.')
    _ensure_tax_office(contact.get('contact_id'), sale.get('selected_contact_name') or v3._display(contact) or sale.get('customer'))
    if _old_sale_send is None:
        raise HTTPException(status_code=500, detail='Aktif SALE gönderim route bulunamadı.')
    return _old_sale_send(scna)


if _old_sale_send is not None:
    for route in app.routes:
        if getattr(route, 'path', None) == '/api/kolaybi/transaction/{scna}/sale/send' and 'POST' in (getattr(route, 'methods', set()) or set()):
            route.endpoint = kb_sale_send_with_tax_guard
            if getattr(route, 'dependant', None) is not None:
                route.dependant.call = kb_sale_send_with_tax_guard
            break

print('[SAMA] KolayBi SALE tax-office guard active: selected/created customer is validated before send')
