import print_audit_patch as print_patch

app = print_patch.app
core = print_patch.core

html = core.HTML

old = '<select id="nBasis" onchange="calcFreight()"><option value="TON">TON</option><option value="KG">KG</option></select>'
new = '<select id="nBasis" onchange="calcFreight()"><option value="KG" selected>KG</option><option value="ADET">ADET</option></select>'

if old in html:
    html = html.replace(old, new, 1)
else:
    html = html.replace('<option value="TON">TON</option><option value="KG">KG</option>', '<option value="KG" selected>KG</option><option value="ADET">ADET</option>', 1)

# calcFreight already handles KG as direct quantity. Treat ADET the same way.
html = html.replace("const qty=nBasis.value==='TON'?Number(nKg.value||0)/1000:Number(nKg.value||0);", "const qty=Number(nKg.value||0);")

core.HTML = html
print('[SAMA] New shipment freight units active: KG default + ADET')
