from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_ENTRY_CASH_DIAGNOSTIC_V1'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

anchor="""# SAMA_CASH_DIAGNOSTIC_V1\n# SAMA_CASH_DIAGNOSTIC_ROUTE_FIX_V2\n\n\n# SAMA_EXIT_CASH_MISSING_FROM_20260830_V1"""
backend="""# SAMA_CASH_DIAGNOSTIC_V1\n# SAMA_CASH_DIAGNOSTIC_ROUTE_FIX_V2\n\n# SAMA_ENTRY_CASH_DIAGNOSTIC_V1\n@app.get('/api/entry-cash-diagnostic/{scna}')\ndef entry_cash_diagnostic(scna:str):\n    key=_normalize_scna_value(scna)\n    c=db()\n    row=c.execute(\"\"\"\n      SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name,\n             t.entry_done,t.entry_cash_handed,t.entry_collection,t.entry_at,\n             t.delivery_time,t.trip_date,t.created_at,t.status,COALESCE(t.is_deleted,0) is_deleted\n      FROM trips t\n      LEFT JOIN drivers d ON d.id=t.driver_id\n      WHERE UPPER(TRIM(t.scna))=UPPER(TRIM(?))\n      LIMIT 1\n    \"\"\",(key,)).fetchone()\n    if not row:\n        c.close(); raise HTTPException(404,'SCNA bulunamadı.')\n    x=dict(row)\n    effective_entry=x.get('entry_at') or x.get('delivery_time') or None\n    reasons=[]\n    if int(x.get('is_deleted') or 0)!=0: reasons.append('Kayıt silinmiş')\n    if int(x.get('entry_done') or 0)!=1: reasons.append('Giriş işlemi tamamlanmamış (entry_done != 1)')\n    if float(x.get('entry_cash_handed') or 0)<=0: reasons.append('Şoförün Teslim Ettiği Para 0 veya boş')\n    if not x.get('entry_at'): reasons.append('entry_at boş. Günlük Kasa DATE(entry_at) kullandığı için muhasebeye düşmez')\n    eligible=(len(reasons)==0)\n    x['effective_entry_date']=effective_entry\n    x['cash_in_eligible']=eligible\n    x['cash_in_block_reasons']=reasons\n    x['accounting_result']='MUHASEBEYE GİRER' if eligible else 'MUHASEBEYE GİRMEZ'\n    c.close(); return x\n\n\n# SAMA_EXIT_CASH_MISSING_FROM_20260830_V1"""
if anchor not in s: raise RuntimeError('backend anchor not found')
s=s.replace(anchor,backend,1)

ui_anchor="""function openCashDiagnostic(){\n const scna=(document.getElementById('cashDiagScna')?.value||'').trim();"""
ui="""function openEntryCashDiagnostic(){\n const scna=(document.getElementById('cashDiagScna')?.value||'').trim();\n if(!scna)return alert('SCNA girin.');\n api('/api/entry-cash-diagnostic/'+encodeURIComponent(scna)).then(x=>{\n   const reasons=(x.cash_in_block_reasons||[]).length?(x.cash_in_block_reasons||[]).join('<br>'):'Yok';\n   openM('Giriş / Muhasebe Tanı — '+(x.scna||scna),`<div class=\"table\"><table><tbody>\n   <tr><th>SCNA</th><td><b>${x.scna||''}</b></td></tr><tr><th>Plaka</th><td>${x.plate||''}</td></tr><tr><th>Şoför</th><td>${x.driver_name||''}</td></tr>\n   <tr><th>Durum</th><td>${x.status||''}</td></tr><tr><th>entry_done</th><td>${x.entry_done}</td></tr>\n   <tr><th>Şoförün Teslim Ettiği Para</th><td><b>${money(x.entry_cash_handed||0)} IQD</b></td></tr><tr><th>Müşteriden Alınan</th><td>${money(x.entry_collection||0)} IQD</td></tr>\n   <tr><th>entry_at</th><td>${fmtDateTime(x.entry_at)}</td></tr><tr><th>delivery_time</th><td>${fmtDateTime(x.delivery_time)}</td></tr><tr><th>trip_date</th><td>${x.trip_date||''}</td></tr><tr><th>created_at</th><td>${fmtDateTime(x.created_at)}</td></tr>\n   <tr><th>Muhasebeye Uygun</th><td><b style=\"color:${x.cash_in_eligible?'#166534':'#b91c1c'}\">${x.cash_in_eligible?'EVET':'HAYIR'}</b></td></tr>\n   <tr><th>Sonuç</th><td><b>${x.accounting_result||''}</b></td></tr><tr><th>Engel Nedeni</th><td>${reasons}</td></tr>\n   </tbody></table></div>`,null);\n }).catch(e=>alert(e.message));\n}\n\nfunction openCashDiagnostic(){\n const scna=(document.getElementById('cashDiagScna')?.value||'').trim();"""
if ui_anchor not in s: raise RuntimeError('ui anchor not found')
s=s.replace(ui_anchor,ui,1)

# Add second diagnostic button next to existing cash diagnostic input/button when present.
btn_anchor='''<button class="btn secondary" onclick="openCashDiagnostic()">Kasa Tanı</button>'''
if btn_anchor in s:
    s=s.replace(btn_anchor,btn_anchor+'\n<button class="btn orange" onclick="openEntryCashDiagnostic()">Giriş / Muhasebe Tanı</button>',1)
else:
    print('warning: cash diagnostic button anchor not found; backend+JS still patched')

p.write_text(s,encoding='utf-8')
print('patched entry cash diagnostic v1')
