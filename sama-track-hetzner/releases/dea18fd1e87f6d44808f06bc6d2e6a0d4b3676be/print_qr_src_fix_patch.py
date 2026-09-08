import print_qr_driver_link_patch as qr_patch

app = qr_patch.app
core = qr_patch.visual.base.core

html = core.HTML
old = '/api/print-qr/${encodeURIComponent(x.scna||\'\')}'
new = '/api/driver-status/qr/${encodeURIComponent(x.scna||\'\')}'
count = html.count(old)
if count:
    html = html.replace(old, new)

core.HTML = html
print(f'[SAMA] Print QR source fixed to driver-status QR endpoint: replacements={count}')
