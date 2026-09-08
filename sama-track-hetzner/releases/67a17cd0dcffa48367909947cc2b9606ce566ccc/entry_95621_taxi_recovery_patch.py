# Targeted data repair for SCNA 95621.
# The operator confirmed a 15,000 IQD taxi expense was entered in Entry OTHER but is missing.
# Run after the final fixed/OTHER integrity patch so WAITING has already been migrated out of OTHER.
# This repair is idempotent and never overwrites a different non-empty OTHER expense.

import entry_fixed_other_kolaybi_final_patch as base

app = base.app
core = base.core


def _txt(v):
    return str(v or '').strip()


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _is_taxi(v):
    s = _txt(v).upper().replace('İ', 'I')
    return 'TAKSI' in s or 'TAXI' in s


def _is_generic(v):
    s = _txt(v).upper().replace('İ', 'I')
    return not s or s in ('OTHER', 'DIGER', 'DİĞER', 'OTHER / DIGER', 'DIGER / OTHER')


def repair_95621_taxi():
    c = core.db()
    changed = False
    action = ''
    try:
        row = c.execute('''SELECT
              COALESCE(entry_other_expense_1,0) o1, COALESCE(entry_other_note_1,'') n1,
              COALESCE(entry_other_expense_2,0) o2, COALESCE(entry_other_note_2,'') n2
            FROM trips WHERE UPPER(TRIM(scna))='95621' LIMIT 1''').fetchone()
        if not row:
            return {'ok': False, 'reason': 'SCNA 95621 not found'}

        # 1) If the taxi note survived but the amount did not, restore the confirmed amount.
        for slot in (1, 2):
            amt = _num(row[f'o{slot}'])
            note = _txt(row[f'n{slot}'])
            if _is_taxi(note):
                if abs(amt - 15000.0) < 0.01:
                    return {'ok': True, 'changed': False, 'slot': slot, 'reason': 'already present'}
                if amt <= 0:
                    c.execute(f'''UPDATE trips SET entry_other_expense_{slot}=15000,
                                  entry_other_note_{slot}='TAKSİ / TAXI',updated_at=CURRENT_TIMESTAMP
                                  WHERE UPPER(TRIM(scna))='95621' ''')
                    changed = True
                    action = f'restored amount in OTHER {slot}'
                    break

        # Re-read after a possible repair above.
        if changed:
            c.commit()
        row = c.execute('''SELECT
              COALESCE(entry_other_expense_1,0) o1, COALESCE(entry_other_note_1,'') n1,
              COALESCE(entry_other_expense_2,0) o2, COALESCE(entry_other_note_2,'') n2
            FROM trips WHERE UPPER(TRIM(scna))='95621' LIMIT 1''').fetchone()

        # 2) If 15,000 survived but its note disappeared, restore only a blank/generic note.
        if not changed:
            for slot in (1, 2):
                amt = _num(row[f'o{slot}'])
                note = _txt(row[f'n{slot}'])
                if abs(amt - 15000.0) < 0.01 and (_is_taxi(note) or _is_generic(note)):
                    if not _is_taxi(note):
                        c.execute(f'''UPDATE trips SET entry_other_note_{slot}='TAKSİ / TAXI',
                                      updated_at=CURRENT_TIMESTAMP
                                      WHERE UPPER(TRIM(scna))='95621' ''')
                        changed = True
                        action = f'restored description in OTHER {slot}'
                    else:
                        return {'ok': True, 'changed': False, 'slot': slot, 'reason': 'already present'}
                    break

        # 3) If the save was lost completely, use only an empty OTHER slot.
        if not changed:
            existing_taxi = any(
                abs(_num(row[f'o{slot}']) - 15000.0) < 0.01 and _is_taxi(row[f'n{slot}'])
                for slot in (1, 2)
            )
            if existing_taxi:
                return {'ok': True, 'changed': False, 'reason': 'already present'}

            empty_slot = 0
            for slot in (1, 2):
                if _num(row[f'o{slot}']) <= 0 and _is_generic(row[f'n{slot}']):
                    empty_slot = slot
                    break
            if empty_slot:
                c.execute(f'''UPDATE trips SET entry_other_expense_{empty_slot}=15000,
                              entry_other_note_{empty_slot}='TAKSİ / TAXI',updated_at=CURRENT_TIMESTAMP
                              WHERE UPPER(TRIM(scna))='95621' ''')
                changed = True
                action = f'recreated missing taxi in OTHER {empty_slot}'
            else:
                print('[SAMA] SCNA 95621 TAXI recovery skipped: both OTHER slots contain different expenses; nothing overwritten')
                return {'ok': False, 'changed': False, 'reason': 'no empty OTHER slot'}

        if changed:
            try:
                c.execute('''INSERT INTO audit_log(action,scna,detail,created_at)
                             VALUES('ENTRY_EXPENSE_REPAIR','95621',?,CURRENT_TIMESTAMP)''',
                          (f'Confirmed 15,000 IQD TAKSİ / TAXI expense: {action}',))
            except Exception:
                pass
            c.commit()
            print(f'[SAMA] SCNA 95621 TAXI recovered: 15,000 IQD ({action})')
        return {'ok': True, 'changed': changed, 'action': action}
    finally:
        c.close()


try:
    TAXI_REPAIR_95621 = repair_95621_taxi()
except Exception as exc:
    TAXI_REPAIR_95621 = {'ok': False, 'error': str(exc)}
    print('[SAMA] SCNA 95621 TAXI recovery warning:', exc)

# Print settlement must use the same itemized return-expense total that the document prints.
# This prevents a dedicated ENTRY OTHER (such as TAXI) from becoming a false driver shortage.
import print_driver_reconcile_entry_other_patch as print_driver_reconcile_entry_other
