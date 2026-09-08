import accounting_db_patch as accounting

app = accounting.app
core = accounting.core


def _plate_autocomplete_fixed(q: str = ""):
    key = str(q or "").strip().upper()
    key_compact = ''.join(ch for ch in key if ch.isalnum())
    if len(key_compact) < 3:
        return []
    like = f"%{key_compact}%"
    c = core.db()
    try:
        rows = []
        seen = set()

        # Master fleet list is authoritative. Do not hide a plate because an old
        # active flag is malformed; the UI can decide whether it is selectable.
        try:
            for r in c.execute("""
                SELECT plate,COALESCE(brand,'') brand,COALESCE(model,'') model,
                       COALESCE(vehicle_type,'') vehicle_type
                FROM fleet_vehicles
                WHERE REPLACE(REPLACE(REPLACE(UPPER(TRIM(plate)),' ',''),'-',''),'.','') LIKE ?
                ORDER BY plate LIMIT 100
            """, (like,)).fetchall():
                d = dict(r); p = str(d.get('plate') or '').strip().upper()
                if p and p not in seen:
                    seen.add(p); rows.append(d)
        except Exception as e:
            print('[SAMA] fleet_vehicles autocomplete warning:', e)

        try:
            for r in c.execute("""
                SELECT plate,'' brand,'' model,'' vehicle_type
                FROM vehicles
                WHERE REPLACE(REPLACE(REPLACE(UPPER(TRIM(plate)),' ',''),'-',''),'.','') LIKE ?
                ORDER BY plate LIMIT 100
            """, (like,)).fetchall():
                d = dict(r); p = str(d.get('plate') or '').strip().upper()
                if p and p not in seen:
                    seen.add(p); rows.append(d)
        except Exception as e:
            print('[SAMA] vehicles autocomplete warning:', e)

        try:
            for r in c.execute("""
                SELECT DISTINCT plate,'' brand,'' model,'' vehicle_type
                FROM trips
                WHERE REPLACE(REPLACE(REPLACE(UPPER(TRIM(plate)),' ',''),'-',''),'.','') LIKE ?
                ORDER BY plate LIMIT 100
            """, (like,)).fetchall():
                d = dict(r); p = str(d.get('plate') or '').strip().upper()
                if p and p not in seen:
                    seen.add(p); rows.append(d)
        except Exception as e:
            print('[SAMA] trips autocomplete warning:', e)

        # Put suffix/ending matches first. Example: 731 -> 21H14731.
        rows.sort(key=lambda d: (0 if ''.join(ch for ch in str(d.get('plate') or '').upper() if ch.isalnum()).endswith(key_compact) else 1, str(d.get('plate') or '')))
        if key_compact == '731':
            print('[SAMA] plate autocomplete 731 matches:', [r.get('plate') for r in rows[:20]])
        return rows[:20]
    finally:
        c.close()


for route in app.routes:
    if getattr(route, 'path', None) == '/api/autocomplete/plates' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _plate_autocomplete_fixed
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _plate_autocomplete_fixed
        break

print('[SAMA] Plate autocomplete V2 active: normalized fleet + vehicles + trips')
