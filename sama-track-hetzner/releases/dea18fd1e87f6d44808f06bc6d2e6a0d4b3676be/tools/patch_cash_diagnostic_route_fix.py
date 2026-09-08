from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_CASH_DIAGNOSTIC_ROUTE_FIX_V2'
if MARK in s:
    print('already patched'); raise SystemExit(0)
old="@app.get('/api/cash-diagnostic/{scna}')\ndef cash_diagnostic(scna:str):"
new="@app.get('/api/cash-out-diagnostic/{scna}')\ndef cash_out_diagnostic(scna:str):"
if old not in s:
    raise RuntimeError('new diagnostic route anchor not found')
s=s.replace(old,new,1)
oldjs="api('/api/cash-diagnostic/'+encodeURIComponent(scna))"
newjs="api('/api/cash-out-diagnostic/'+encodeURIComponent(scna))"
if oldjs not in s:
    raise RuntimeError('diagnostic JS route anchor not found')
s=s.replace(oldjs,newjs,1)
anchor="# SAMA_CASH_DIAGNOSTIC_V1"
s=s.replace(anchor,anchor+'\n'+MARK,1)
p.write_text(s,encoding='utf-8')
print('patched cash diagnostic route collision')
