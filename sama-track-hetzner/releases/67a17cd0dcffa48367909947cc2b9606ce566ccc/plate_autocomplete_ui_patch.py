import plate_autocomplete_patch as plate_patch

core = plate_patch.core
app = plate_patch.app
html = core.HTML

old = '<input id="nPlate" placeholder="En az 3 karakter yazın" oninput="newTripPlateDriverSync()">'
new = '<input id="nPlate" placeholder="En az 3 karakter yazın" onfocus="samaAttachAutocomplete(this,\'plate\')" oninput="newTripPlateDriverSync()">'
if old in html:
    html = html.replace(old, new, 1)

core.HTML = html
print('[SAMA] New shipment plate autocomplete UI hook active')
