from io import BytesIO

from fastapi import Request
from fastapi.responses import Response

import driver_qr_visual_patch as visual

app = visual.app
base = visual.base


def _driver_qr_for_print(scna: str, request: Request):
    import qrcode

    key = str(scna or '').strip().upper()
    link = str(request.base_url).rstrip('/') + '/driver-status/' + base._token(key)
    img = qrcode.make(link)
    out = BytesIO()
    img.save(out, format='PNG')
    return Response(out.getvalue(), media_type='image/png', headers={'Cache-Control': 'no-store'})


patched = False
for route in app.routes:
    if getattr(route, 'path', None) == '/api/print-qr/{scna}' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _driver_qr_for_print
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _driver_qr_for_print
        patched = True
        break

if not patched:
    app.add_api_route('/api/print-qr/{scna}', _driver_qr_for_print, methods=['GET'])

print('[SAMA] Printed shipment QR now opens driver visual status page')
