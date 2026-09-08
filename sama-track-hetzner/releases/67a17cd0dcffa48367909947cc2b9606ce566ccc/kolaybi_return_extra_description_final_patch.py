# Final backend-only fix for legacy RETURN EXTRA / OTHER descriptions.
# These old entry_extra_expense_1..3 rows predate the dedicated OTHER note fields.
# Keep login/HTML untouched. Apply the description at the final PURCHASE preview layer
# and at the underlying web preview so the same text is also sent to KolayBi.
import re

import kolaybi_serial_manual_sent_sync_patch as base
import kolaybi_web_module_patch as webmod
import kolaybi_workflow_v2_patch as workflow

app = base.app
core = base.core


def _txt(v):
    return str(v or '').strip()


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _generic_return_text(v):
    s = _txt(v).upper()
    return (not s) or s.startswith('RETURN EXTRA EXPENSE') or s in ('OTHER', 'OTHER / OTHER', 'DİĞER', 'DIGER')


# Give the legacy amount fields their own persistent notes from now on.
c = core.db()
try:
    for slot in (1, 2, 3):
        core.addcol(c, 'trips', f'entry_extra_note_{slot}', "TEXT DEFAULT ''")
    c.commit()
finally:
    c.close()


def _description_sources(scna):
    key = _txt(scna)
    c = core.db()
    try:
        row = c.execute('''
            SELECT
              COALESCE(entry_extra_expense_1,0) entry_extra_expense_1,
              COALESCE(entry_extra_expense_2,0) entry_extra_expense_2,
              COALESCE(entry_extra_expense_3,0) entry_extra_expense_3,
              COALESCE(entry_extra_note_1,'') entry_extra_note_1,
              COALESCE(entry_extra_note_2,'') entry_extra_note_2,
              COALESCE(entry_extra_note_3,'') entry_extra_note_3,
              COALESCE(entry_other_expense_1,0) entry_other_expense_1,
              COALESCE(entry_other_expense_2,0) entry_other_expense_2,
              COALESCE(entry_other_note_1,'') entry_other_note_1,
              COALESCE(entry_other_note_2,'') entry_other_note_2,
              COALESCE(entry_note,'') entry_note
            FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))
        ''', (key,)).fetchone()
        if not row:
            return {}, ''
        row = dict(row)

        labels = {}
        try:
            exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='trip_entry_expense_labels'").fetchone()
            if exists:
                for r in c.execute('''SELECT slot,label FROM trip_entry_expense_labels
                                      WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (key,)).fetchall():
                    label = _txt(r['label'])
                    if label and not _generic_return_text(label):
                        labels[int(r['slot'])] = label
        except Exception:
            labels = {}

        out = {}
        for slot in (1, 2, 3):
            if _num(row.get(f'entry_extra_expense_{slot}')) <= 0:
                continue
            # Priority: dedicated legacy note > surviving expense label > the newer
            # OTHER note in the same slot (only if its own amount is zero) > general entry note.
            note = _txt(row.get(f'entry_extra_note_{slot}'))
            source = 'entry_extra_note'
            if not note:
                note = labels.get(slot, '')
                source = 'trip_entry_expense_labels'
            if not note and slot in (1, 2) and _num(row.get(f'entry_other_expense_{slot}')) <= 0:
                note = _txt(row.get(f'entry_other_note_{slot}'))
                source = 'entry_other_note'
            if not note:
                note = _txt(row.get('entry_note'))
                source = 'entry_note'
            if note:
                out[slot] = {'description': note, 'source': source}
        return out, _txt(row.get('entry_note'))
    finally:
        c.close()


def _apply_return_descriptions(scna, preview):
    if not isinstance(preview, dict):
        return preview
    sources, _entry_note = _description_sources(scna)
    for item in preview.get('items') or []:
        raw_slot = item.get('return_extra_slot')
        try:
            slot = int(raw_slot or 0)
        except Exception:
            slot = 0
        if slot not in (1, 2, 3):
            continue
        src = sources.get(slot)
        if src:
            item['description'] = src['description']
            item['description_source'] = 'SAMA ' + src['source']
        elif _generic_return_text(item.get('description')):
            # Do not pretend that the generic technical slot name is a real description.
            item['description'] = 'AÇIKLAMA GİRİLMEMİŞ / DESCRIPTION MISSING'
            item['description_source'] = 'MISSING'
    return preview


# Underlying preview: fixes direct preview and any sender that reads webmod directly.
_original_web_preview = webmod.kolaybi_preview


def _web_preview_with_final_return_notes(scna):
    return _apply_return_descriptions(scna, _original_web_preview(scna))


webmod.kolaybi_preview = _web_preview_with_final_return_notes

# Final PURCHASE preview: guarantees the single-SCNA KolayBi table sees the same text,
# even if an older wrapper captured a previous preview callable.
_original_purchase_preview = workflow._purchase_preview


def _purchase_preview_with_final_return_notes(scna, trip=None):
    return _apply_return_descriptions(scna, _original_purchase_preview(scna, trip))


workflow._purchase_preview = _purchase_preview_with_final_return_notes

# Small API for future/per-record corrections without touching the shipment amounts.
@app.get('/api/trips/{scna}/entry-extra-descriptions')
def get_entry_extra_descriptions(scna: str):
    key = _txt(scna)
    c = core.db()
    try:
        row = c.execute('''SELECT entry_extra_expense_1,entry_extra_expense_2,entry_extra_expense_3,
                                  entry_extra_note_1,entry_extra_note_2,entry_extra_note_3
                           FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''', (key,)).fetchone()
        if not row:
            return []
        return [
            {'slot': slot, 'amount': _num(row[f'entry_extra_expense_{slot}']), 'description': _txt(row[f'entry_extra_note_{slot}'])}
            for slot in (1, 2, 3)
        ]
    finally:
        c.close()

print('[SAMA] FINAL RETURN EXTRA description fix active: legacy OTHER lines use saved/label/OTHER/general entry notes instead of technical RETURN EXTRA names')
