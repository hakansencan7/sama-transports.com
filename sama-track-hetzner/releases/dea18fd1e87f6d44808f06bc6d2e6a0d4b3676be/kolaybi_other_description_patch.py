# Backend-only fix: preserve the real SAMA OTHER explanations on KolayBi item lines.
# Do not touch core.HTML/login JavaScript.
import kolaybi_remote_sent_backend_safe_patch as base
import kolaybi_web_module_patch as webmod

app = base.app
core = base.core


def _txt(v):
    return str(v or '').strip()


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _same_amount(a, b):
    return abs(_num(a) - _num(b)) < 0.000001


# Capture the FINAL preview function after all purchase/return-extra wrappers.
_original_preview = webmod.kolaybi_preview


def _preview_with_real_other_descriptions(scna: str):
    pv = _original_preview(scna)

    c = core.db()
    try:
        row = c.execute('''
            SELECT exit_other, exit_other_note,
                   COALESCE(entry_other_expense_1,0) AS entry_other_expense_1,
                   COALESCE(entry_other_expense_2,0) AS entry_other_expense_2,
                   COALESCE(entry_other_note_1,'') AS entry_other_note_1,
                   COALESCE(entry_other_note_2,'') AS entry_other_note_2,
                   COALESCE(entry_note,'') AS entry_note
            FROM trips
            WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))
        ''', (_txt(scna),)).fetchone()
    finally:
        c.close()

    if not row:
        return pv

    items = pv.get('items') or []

    # 1) EXIT OTHER: this was the real bug. The old web preview replaced the stored
    #    explanation with a generic 'EXIT OTHER EXPENSE' text. Restore exit_other_note.
    exit_amount = _num(row['exit_other'])
    exit_note = _txt(row['exit_other_note'])
    if exit_amount > 0 and exit_note:
        candidates = []
        for item in items:
            if _txt(item.get('code')).upper() != 'OTHER':
                continue
            desc = _txt(item.get('description')).upper()
            source = _txt(item.get('source')).upper()
            if 'RETURN EXTRA' in source:
                continue
            if ('EXIT OTHER' in desc or 'ÇIKIŞ OTHER' in desc or 'CIKIS OTHER' in desc or
                'ÇIKIŞ DİĞER' in desc or 'CIKIS DIGER' in desc):
                candidates.append(item)
        # Fallback only when there is one amount-identical blank/generic OTHER line.
        if not candidates:
            for item in items:
                if _txt(item.get('code')).upper() != 'OTHER':
                    continue
                if not _same_amount(item.get('total'), exit_amount):
                    continue
                if 'RETURN EXTRA' in _txt(item.get('source')).upper():
                    continue
                desc = _txt(item.get('description'))
                if not desc or desc.upper() in ('OTHER', 'DİĞER', 'DIGER'):
                    candidates.append(item)
        if len(candidates) == 1:
            candidates[0]['description'] = exit_note
            candidates[0]['description_source'] = 'SAMA exit_other_note'

    # 2) ENTRY OTHER 1/2 already carry their note in the normal preview path.
    #    Reinforce it here for old/partially migrated rows where the description was lost.
    for slot in (1, 2):
        amount = _num(row[f'entry_other_expense_{slot}'])
        note = _txt(row[f'entry_other_note_{slot}'])
        if amount <= 0 or not note:
            continue
        if any(_txt(i.get('description')) == note for i in items if _txt(i.get('code')).upper() == 'OTHER'):
            continue
        possible = []
        for item in items:
            if _txt(item.get('code')).upper() != 'OTHER':
                continue
            if not _same_amount(item.get('total'), amount):
                continue
            if 'RETURN EXTRA' in _txt(item.get('source')).upper():
                continue
            desc = _txt(item.get('description'))
            if not desc or desc.upper() in ('OTHER', 'DİĞER', 'DIGER'):
                possible.append(item)
        if len(possible) == 1:
            possible[0]['description'] = note
            possible[0]['description_source'] = f'SAMA entry_other_note_{slot}'

    # 3) Old/imported RETURN EXTRA rows can exist only as generic OTHER items.
    #    SAMA's own print path already treats entry_note as the explanation for those
    #    legacy rows, so use the same proven meaning here when no specific label survived.
    legacy_note = _txt(row['entry_note'])
    if legacy_note:
        for item in items:
            if _txt(item.get('code')).upper() != 'OTHER':
                continue
            if 'LEGACY RETURN EXTRA FALLBACK' not in _txt(item.get('source')).upper():
                continue
            desc = _txt(item.get('description')).upper()
            if desc.startswith('RETURN EXTRA EXPENSE') or not desc:
                item['description'] = legacy_note
                item['description_source'] = 'SAMA entry_note legacy fallback'

    return pv


# The purchase sender resolves webmod.kolaybi_preview at call time, so this one
# assignment fixes BOTH the preview and the actual KolayBi items[i][description] payload.
webmod.kolaybi_preview = _preview_with_real_other_descriptions

# Keep the direct preview route aligned as well.
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/preview/{scna}' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _preview_with_real_other_descriptions
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _preview_with_real_other_descriptions
        break

print('[SAMA] KolayBi OTHER description fix active: EXIT uses exit_other_note; ENTRY OTHER uses its notes; legacy RETURN EXTRA can use entry_note; no HTML/login changes')
