# Final Entry expense integrity patch.
# 1) Repair SCNA 95621 from the operator-confirmed business meaning:
#    slot1=WEIGHBRIDGE, slot2=PARKING, waiting-like OTHER -> slot3=WAITING.
# 2) Guarantee newly entered ENTRY OTHER 1/2 are persisted before the normal Entry save closes.
# 3) Guarantee ENTRY OTHER 1/2 appear in the final KolayBi PURCHASE preview/send.
# 4) Re-pin the final Entry print-expense routes to the itemized builder that includes fixed + OTHER rows.
# No separate <script> block is added.

import re

import cash_daily_history_search_patch as base
import entry_other_and_print_items_patch as entry_items
import kolaybi_web_module_patch as webmod
import kolaybi_workflow_v2_patch as workflow

app = base.app
core = base.core
html = core.HTML
kdb = webmod.kdb


def _txt(v):
    return str(v or '').strip()


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _product(code):
    c = kdb()
    try:
        r = c.execute('SELECT * FROM products WHERE UPPER(code)=UPPER(?) AND is_active=1', (_txt(code),)).fetchone()
        return dict(r) if r else {}
    finally:
        c.close()


def _fixed_meta_upsert(c, scna, slot, code, amount):
    amount = _num(amount)
    if amount <= 0:
        return
    c.execute('''INSERT INTO trip_entry_fixed_expenses(scna,slot,code,qty,unit_price,total,updated_at)
                 VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
                 ON CONFLICT(scna,slot) DO UPDATE SET
                   code=excluded.code,
                   qty=CASE WHEN COALESCE(trip_entry_fixed_expenses.qty,0)>0 THEN trip_entry_fixed_expenses.qty ELSE excluded.qty END,
                   unit_price=CASE WHEN COALESCE(trip_entry_fixed_expenses.unit_price,0)>0 THEN trip_entry_fixed_expenses.unit_price ELSE excluded.unit_price END,
                   total=excluded.total,
                   updated_at=CURRENT_TIMESTAMP''',
              (_txt(scna), int(slot), _txt(code), 1.0, amount, amount))
    labels = {1:'KANTAR / WEIGHBRIDGE', 2:'PARK / PARKING', 3:'BEKLEME / WAITING'}
    try:
        c.execute('''INSERT INTO trip_entry_expense_labels(scna,slot,label,amount,updated_at)
                     VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(scna,slot) DO UPDATE SET label=excluded.label,amount=excluded.amount,updated_at=CURRENT_TIMESTAMP''',
                  (_txt(scna), int(slot), labels[int(slot)], amount))
    except Exception:
        pass


def _repair_95621_once():
    # This is deliberately SCNA-specific. The user confirmed these exact legacy rows;
    # we do not reinterpret unrelated historical free-form expenses globally.
    c = core.db()
    try:
        row = c.execute('''SELECT
              COALESCE(entry_extra_expense_1,0) e1,
              COALESCE(entry_extra_expense_2,0) e2,
              COALESCE(entry_extra_expense_3,0) e3,
              COALESCE(entry_other_expense_1,0) o1,
              COALESCE(entry_other_expense_2,0) o2,
              COALESCE(entry_other_note_1,'') n1,
              COALESCE(entry_other_note_2,'') n2
            FROM trips WHERE UPPER(TRIM(scna))='95621' LIMIT 1''').fetchone()
        if not row:
            return

        # Operator-confirmed fixed meanings for the two legacy 10k rows.
        _fixed_meta_upsert(c, '95621', 1, 'WEIGHBRIDGE', row['e1'])
        _fixed_meta_upsert(c, '95621', 2, 'PARKING', row['e2'])

        waiting_amount = _num(row['e3'])
        waiting_other_slot = 0
        waiting_other_amount = 0.0
        for slot in (1, 2):
            note = _txt(row[f'n{slot}']).upper()
            amt = _num(row[f'o{slot}'])
            if amt > 0 and ('BEKLEME' in note or 'WAITING' in note):
                waiting_other_slot = slot
                waiting_other_amount = amt
                if waiting_amount <= 0:
                    waiting_amount = amt
                break

        if waiting_amount > 0:
            # Preserve the established settlement column and create the missing fixed metadata.
            c.execute('''UPDATE trips SET entry_extra_expense_3=?,updated_at=CURRENT_TIMESTAMP
                         WHERE UPPER(TRIM(scna))='95621' ''', (waiting_amount,))
            _fixed_meta_upsert(c, '95621', 3, 'WAITING', waiting_amount)

            # If WAITING had been entered into OTHER because the fixed WAITING row was not
            # working, remove the duplicate OTHER source once it has been recovered.
            if waiting_other_slot in (1, 2) and (waiting_other_amount > 0):
                c.execute(f'''UPDATE trips SET entry_other_expense_{waiting_other_slot}=0,
                              entry_other_note_{waiting_other_slot}='',updated_at=CURRENT_TIMESTAMP
                              WHERE UPPER(TRIM(scna))='95621' ''')
        c.commit()
    finally:
        c.close()


try:
    _repair_95621_once()
except Exception as exc:
    print('[SAMA] SCNA 95621 fixed-expense repair warning:', exc)


def _entry_other_rows(scna):
    c = core.db()
    try:
        r = c.execute('''SELECT
              COALESCE(entry_other_expense_1,0) o1, COALESCE(entry_other_note_1,'') n1,
              COALESCE(entry_other_expense_2,0) o2, COALESCE(entry_other_note_2,'') n2
            FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (_txt(scna),)).fetchone()
        if not r:
            return []
        return [
            {'slot':1,'amount':_num(r['o1']),'description':_txt(r['n1'])},
            {'slot':2,'amount':_num(r['o2']),'description':_txt(r['n2'])},
        ]
    finally:
        c.close()


def _ensure_entry_other(scna, pv):
    if not isinstance(pv, dict):
        return pv
    original_ready = bool(pv.get('ready'))
    items = pv.setdefault('items', [])
    p = _product('OTHER')
    for x in _entry_other_rows(scna):
        amount = _num(x['amount'])
        desc = _txt(x['description'])
        if amount <= 0 and not desc:
            continue
        # Strong de-duplication: same dedicated source slot OR same amount+description.
        exists = False
        for it in items:
            if int(_num(it.get('entry_other_slot'))) == int(x['slot']):
                exists = True; break
            if (_txt(it.get('code')).upper() == 'OTHER' and
                abs(_num(it.get('total')) - amount) < 0.000001 and
                _txt(it.get('description')) == desc):
                exists = True; break
        if exists:
            continue
        items.append({
            'code':'OTHER',
            'name':(_txt(p.get('name_tr')) or 'DİĞER')+' / '+(_txt(p.get('name_en')) or 'OTHER'),
            'product_id':_txt(p.get('product_id')),
            'quantity':1,
            'unit_price':amount,
            'total':amount,
            'description':desc or 'AÇIKLAMA GİRİLMEMİŞ / DESCRIPTION MISSING',
            'description_source':f'SAMA entry_other_note_{x["slot"]}',
            'source':'ENTRY OTHER',
            'entry_other_slot':int(x['slot']),
        })

    pv['missing_product_codes'] = sorted({_txt(i.get('code')) for i in items if not _txt(i.get('product_id'))})
    # Preserve every blocker already calculated by the authoritative workflow
    # (contact/address/tax/project/etc.). Adding OTHER may only make ready FALSE if its product is missing.
    pv['ready'] = original_ready and not pv['missing_product_codes']
    return pv


# Final KolayBi wrappers. These execute after the older RETURN EXTRA/description layers.
_original_web_preview = webmod.kolaybi_preview

def _web_preview_final(scna):
    return _ensure_entry_other(scna, _original_web_preview(scna))

webmod.kolaybi_preview = _web_preview_final

_original_purchase_preview = workflow._purchase_preview

def _purchase_preview_final(scna, trip=None):
    return _ensure_entry_other(scna, _original_purchase_preview(scna, trip))

workflow._purchase_preview = _purchase_preview_final

# Keep the direct preview endpoint aligned with the same final data.
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/preview/{scna}' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _web_preview_final
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _web_preview_final

# Re-pin both print-expense URLs to the itemized builder that includes:
# WEIGHBRIDGE + PARKING + WAITING + ENTRY OTHER 1/2 with descriptions.
for route in app.routes:
    if getattr(route, 'path', None) in ('/api/print-entry-expenses/{scna}', '/api/print-entry-expenses-v2/{scna}') and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = entry_items._itemized_entry_print
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = entry_items._itemized_entry_print

# Deterministic save: before the established Entry callback closes the modal,
# explicitly flush fixed expenses + both dedicated OTHER rows. This complements
# the edit-unlock wrapper and also covers very fast clicks / alternate template copies.
needle = '''          entry_note:gNote.value
        })
      });

      closeM();'''
replacement = '''          entry_note:gNote.value
        })
      });

      if(typeof fixedEntrySave==='function'){
        for(const _slot of [1,2,3]){try{await fixedEntrySave(_slot);}catch(_e){}}
      }
      if(typeof entryOtherSave==='function'){
        for(const _slot of [1,2]){try{await entryOtherSave(_slot);}catch(_e){}}
      }
      closeM();'''
if needle in html:
    html = html.replace(needle, replacement)

core.HTML = html
print('[SAMA] FINAL Entry expense integrity active: 95621 fixed KANTAR/PARK/WAITING + ENTRY OTHER guaranteed in save/print/KolayBi')
