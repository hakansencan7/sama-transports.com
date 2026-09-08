from fastapi import HTTPException, Request
import driver_qr_status_patch as base

app = base.app
core = base.core
DriverReviewIn = base.DriverReviewIn
VALID_DRIVER = base.VALID_DRIVER


def _driver_status_review_synced(report_id: int, body: DriverReviewIn, request: Request):
    action = str(body.action or '').strip().upper()
    if action not in ('APPROVE','REJECT'):
        raise HTTPException(400, 'İşlem APPROVE veya REJECT olmalı.')

    c = core.db()
    try:
        row = c.execute('SELECT * FROM driver_status_reports WHERE id=?', (report_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Bildirim bulunamadı.')
        if row['review_state'] != 'PENDING':
            raise HTTPException(409, 'Bu bildirim daha önce değerlendirildi.')

        approved = str(body.approved_status or row['reported_status'] or '').strip().upper()
        if approved not in VALID_DRIVER:
            approved = row['reported_status']

        user = getattr(request.state, 'auth_user', None) or {}
        reviewer = str(user.get('full_name') or user.get('username') or '').strip()
        new_state = 'APPROVED' if action == 'APPROVE' else 'REJECTED'

        c.execute(
            '''UPDATE driver_status_reports
               SET review_state=?,approved_status=?,reviewer_note=?,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=?
               WHERE id=?''',
            (new_state, approved if action == 'APPROVE' else '', str(body.note or '').strip(), reviewer, report_id),
        )

        if action == 'APPROVE':
            label = VALID_DRIVER.get(approved, approved)

            # Main Operations screen uses vehicle_operations.gps_state='DONUYOR'
            # to render the vehicle as DONUYOR. Keep the driver's report separate
            # until the GPS/operator approves it, then synchronize that field.
            gps_state = 'DONUYOR' if approved == 'RETURNING' else ''

            c.execute(
                '''INSERT INTO vehicle_operations(plate,load_state,queue_no,vessel,operation_note,vessel_state,gps_state,updated_at)
                   VALUES(?, 'BOS',0,'',?,'',?,CURRENT_TIMESTAMP)
                   ON CONFLICT(plate) DO UPDATE SET
                     operation_note=excluded.operation_note,
                     gps_state=excluded.gps_state,
                     updated_at=CURRENT_TIMESTAMP''',
                (row['plate'], 'ŞOFÖR QR: ' + label, gps_state),
            )

            try:
                core.audit('GPS_STATE', row['plate'], gps_state or 'TEMIZLENDI', 'FILO')
            except Exception:
                pass

        c.commit()
    finally:
        c.close()

    return {
        'ok': True,
        'review_state': new_state,
        'approved_status': approved if action == 'APPROVE' else '',
        'main_operation_state': 'DONUYOR' if action == 'APPROVE' and approved == 'RETURNING' else '',
    }


patched = False
for route in app.routes:
    if getattr(route, 'path', None) == '/api/driver-status/reports/{report_id}/review' and 'POST' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _driver_status_review_synced
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _driver_status_review_synced
        patched = True
        break

print(f'[SAMA] Driver review -> main operation state sync active: patched={1 if patched else 0}')
