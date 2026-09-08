import re

import kolaybi_web_module_patch as webmod
import kolaybi_legacy_invoice_items_patch as legacy

app = legacy.app
core = legacy.core
kdb = legacy.kdb


def _txt(v):
    return str(v or '').strip()


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _norm(v):
    s = _txt(v).upper()
    s = (s.replace('İ', 'I').replace('Ş', 'S').replace('Ğ', 'G')
           .replace('Ü', 'U').replace('Ö', 'O').replace('Ç', 'C'))
    return re.sub(r'[^A-Z0-9]+', '', s)


def _product(code):
    c = kdb()
    try:
        row = c.execute('SELECT * FROM products WHERE UPPER(code)=UPPER(?) AND is_active=1', (_txt(code),)).fetchone()
        return dict(row) if row else {}
    finally:
        c.close()


def _label_code(label):
    n = _norm(label)
    if any(x in n for x in ('WEIGHBRIDGE', 'WEIGHTBRIDGE', 'WEIGHTBRIGE', 'KANTAR')):
        return 'WEIGHBRIDGE'
    if any(x in n for x in ('PARKING', 'PARK', 'OTOPARK')):
        return 'PARKING'
    if any(x in n for x in ('WAITING', 'BEKLEME')):
        return 'WAITING'
    return 'OTHER'


def _fallback_item(slot, amount, label):
    code = _label_code(label)
    p = _product(code)
    tr_name = _txt(p.get('name_tr')) or ('DİĞER' if code == 'OTHER' else code)
    en_name = _txt(p.get('name_en')) or ('OTHER' if code == 'OTHER' else code)
    desc = _txt(label) or f'RETURN EXTRA EXPENSE {slot}'
    if code == 'OTHER' and 'RETURN EXTRA' not in desc.upper():
        desc = f'RETURN EXTRA EXPENSE {slot} / {desc}'
    return {
        'code': code,
        'name': tr_name + ' / ' + en_name,
        'product_id': _txt(p.get('product_id')),
        'quantity': 1,
        'unit_price': _num(amount),
        'total': _num(amount),
        'description': desc,
        'source': 'LEGACY RETURN EXTRA FALLBACK',
        'return_extra_slot': int(slot),
    }


def _return_extra_fallbacks(scna):
    key = _txt(scna)
    c = core.db()
    try:
        trip = c.execute('''SELECT entry_extra_expense_1,entry_extra_expense_2,entry_extra_expense_3
                            FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (key,)).fetchone()
        if not trip:
            return []

        fixed_slots = set()
        try:
            fixed_slots = {int(r['slot']) for r in c.execute('''SELECT slot FROM trip_entry_fixed_expenses
                                                                 WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (key,)).fetchall()}
        except Exception:
            fixed_slots = set()

        labels = {}
        try:
            exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='trip_entry_expense_labels'").fetchone()
            if exists:
                for r in c.execute('''SELECT slot,label FROM trip_entry_expense_labels
                                      WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (key,)).fetchall():
                    labels[int(r['slot'])] = _txt(r['label'])
        except Exception:
            labels = {}

        out = []
        for slot in (1, 2, 3):
            amount = _num(trip[f'entry_extra_expense_{slot}'])
            if amount <= 0:
                continue
            # New-format entries already live in trip_entry_fixed_expenses and are
            # included by the normal KolayBi preview. Only recover old/imported rows.
            if slot in fixed_slots:
                continue
            label = labels.get(slot) or f'RETURN EXTRA EXPENSE {slot}'
            out.append(_fallback_item(slot, amount, label))
        return out
    finally:
        c.close()


_original_preview = webmod.kolaybi_preview


def _preview_with_return_extra(scna):
    pv = _original_preview(scna)
    items = pv.setdefault('items', [])
    recovered = _return_extra_fallbacks(scna)

    # Do not duplicate a fallback if another patch already recovered the same slot.
    present_slots = {int(x.get('return_extra_slot')) for x in items if _txt(x.get('return_extra_slot')).isdigit()}
    for item in recovered:
        if int(item['return_extra_slot']) not in present_slots:
            items.append(item)

    pv['return_extra_fallbacks'] = recovered
    pv['missing_product_codes'] = sorted({_txt(x.get('code')) for x in items if not _txt(x.get('product_id'))})
    return pv


webmod.kolaybi_preview = _preview_with_return_extra

# Keep the direct preview endpoint aligned with the transaction PURCHASE preview.
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/preview/{scna}' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _preview_with_return_extra
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _preview_with_return_extra
        break

print('[SAMA] KolayBi PURCHASE return-extra fallback active: legacy/imported entry_extra_expense_1..3 are invoice items')
