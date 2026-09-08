import kolaybi_contact_resolution_v3_patch as v3

app = v3.app
core = v3.core


def _txt(v):
    return str(v or '').strip()


def _norm(v):
    return v3._norm(v)


def _purchase_candidates_freight_first(plate, rows):
    """Choose the operational FREIGHT cari for a plate before REPAIR/service caris.

    KolayBi can contain multiple associates for one truck, e.g.
    `22B37638 FREIGHT SCANIA` and `22B37638 REPAIR SCANIA`.
    PURCHASE invoices belong to the FREIGHT/transport cari, not the repair cari.
    """
    target = _norm(plate)
    scored = {}
    for row in rows:
        cid = _txt(row.get('contact_id'))
        if not cid:
            continue

        raw_fields = [
            row.get('plate'), row.get('name'), row.get('full_name'),
            row.get('key'), row.get('source_code')
        ]
        vals = [_norm(x) for x in raw_fields if _txt(x)]
        joined = ''.join(vals)
        if not any(target and target in v for v in vals):
            continue

        score = 0
        # Exact plate remains important.
        if _norm(row.get('plate')) == target:
            score += 120

        # The old working business rule is FREIGHT {PLATE}. Accept either word order
        # because KolayBi names may be `FREIGHT 22B...` or `22B... FREIGHT SCANIA`.
        has_freight = any('FREIGHT' in v for v in vals)
        has_repair = any(x in joined for x in ('REPAIR','SERVIS','SERVICE','BAKIM','ATOLYE','WORKSHOP'))
        if has_freight:
            score += 500
        if has_repair:
            score -= 300

        # Strong bonus for a field containing both the target plate and FREIGHT.
        if any(target in v and 'FREIGHT' in v for v in vals):
            score += 250

        note = _txt(row.get('note'))
        if note and not note.startswith('KolayBi API'):
            score += 50
        if _txt(row.get('address_id')):
            score += 20
        if v3._active(row):
            score += 5

        prev = scored.get(cid)
        if not prev or score > prev[0]:
            scored[cid] = (score, row)

    return sorted(scored.values(), key=lambda x: (x[0], _txt(x[1].get('updated_at'))), reverse=True)


# Replace the scorer used by _resolve_purchase. The resolver itself, detail/address
# enrichment and all send guards remain unchanged.
v3._purchase_candidates = _purchase_candidates_freight_first

print('[SAMA] KolayBi PURCHASE cari priority active: FREIGHT plate cari wins over REPAIR/SERVICE cari')
