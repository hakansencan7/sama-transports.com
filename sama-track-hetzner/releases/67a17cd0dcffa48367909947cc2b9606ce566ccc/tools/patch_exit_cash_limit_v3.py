from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_EXIT_CASH_LIMIT_V3'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

anchor='# SAMA_EXIT_CASH_MISSING_EXPENSES_V2'
if anchor not in s:
    raise RuntimeError('expense details v2 marker not found')
s=s.replace(anchor, anchor+'\n'+MARK, 1)

old="""    row=c.execute(\"SELECT scna,exit_done,exit_cash FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) AND COALESCE(is_deleted,0)=0 LIMIT 1\",(key,)).fetchone()\n    if not row:\n        c.close(); raise HTTPException(404,'SCNA bulunamadı.')\n    if int(row['exit_done'] or 0)!=1:\n        c.close(); raise HTTPException(400,'Bu sevkiyatın çıkış işlemi tamamlanmamış.')\n    c.execute(\"UPDATE trips SET exit_cash=?,updated_at=CURRENT_TIMESTAMP WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))\",(amount,key))"""
new="""    row=c.execute(\"\"\"\n      SELECT scna,exit_done,exit_cash,\n             COALESCE(exit_official_fuel_total,0) exit_official_fuel_total,\n             COALESCE(exit_commercial_fuel_total,0) exit_commercial_fuel_total,\n             COALESCE(exit_baghdad_fuel_total,0) exit_baghdad_fuel_total,\n             COALESCE(exit_allowance,0) exit_allowance,\n             COALESCE(exit_premium,0) exit_premium,\n             COALESCE(exit_other,0) exit_other,\n             COALESCE(dock_fee,0) dock_fee,\n             COALESCE(port_fee,0) port_fee,\n             COALESCE(sonar,0) sonar\n      FROM trips\n      WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) AND COALESCE(is_deleted,0)=0\n      LIMIT 1\n    \"\"\",(key,)).fetchone()\n    if not row:\n        c.close(); raise HTTPException(404,'SCNA bulunamadı.')\n    if int(row['exit_done'] or 0)!=1:\n        c.close(); raise HTTPException(400,'Bu sevkiyatın çıkış işlemi tamamlanmamış.')\n    allowed_total=sum(float(row[k] or 0) for k in (\n        'exit_official_fuel_total','exit_commercial_fuel_total','exit_baghdad_fuel_total',\n        'exit_allowance','exit_premium','exit_other','dock_fee','port_fee','sonar'\n    ))\n    if allowed_total>0 and amount>allowed_total+0.01:\n        c.close()\n        raise HTTPException(400,f'HATA: Şoföre verilen nakit gider toplamını aşamaz. Gider toplamı {allowed_total:,.0f} IQD, girilen {amount:,.0f} IQD.')\n    c.execute(\"UPDATE trips SET exit_cash=?,updated_at=CURRENT_TIMESTAMP WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))\",(amount,key))"""
if old not in s:
    raise RuntimeError('backend exit cash save anchor not found')
s=s.replace(old,new,1)

old_btn="""<td><button class=\"btn orange\" onclick=\"saveMissingExitCash('${String(x.scna).replace(/'/g,\"\\\\'\")}')\">Kaydet</button></td>"""
new_btn="""<td><button class=\"btn orange\" onclick=\"saveMissingExitCash('${String(x.scna).replace(/'/g,\"\\\\'\")}',Number(x.visible_expense_total||0))\">Kaydet</button></td>"""
if old_btn not in s:
    raise RuntimeError('save button anchor not found')
s=s.replace(old_btn,new_btn,1)

old_func="""async function saveMissingExitCash(scna){\n  const id='missingCash_'+String(scna).replace(/[^A-Za-z0-9_]/g,'_');\n  const el=document.getElementById(id);\n  const amount=Number(String(el?.value||'').replace(/\\./g,'').replace(',','.'));\n  if(!amount||amount<=0){alert('Şoföre verilen toplam nakdi girin.');return;}\n  if(!confirm(scna+' için şoföre verilen toplam nakit '+money(amount)+' IQD olarak kaydedilsin mi?'))return;"""
new_func="""async function saveMissingExitCash(scna,allowedTotal=0){\n  const id='missingCash_'+String(scna).replace(/[^A-Za-z0-9_]/g,'_');\n  const el=document.getElementById(id);\n  const amount=Number(String(el?.value||'').replace(/\\./g,'').replace(',','.'));\n  if(!amount||amount<=0){alert('Şoföre verilen toplam nakdi girin.');return;}\n  allowedTotal=Number(allowedTotal||0);\n  if(allowedTotal>0 && amount>allowedTotal+0.01){\n    alert('HATA: Fazla para girdiniz.\\n\\nGider toplamı: '+money(allowedTotal)+' IQD\\nGirilen: '+money(amount)+' IQD\\nFazla: '+money(amount-allowedTotal)+' IQD\\n\\nKayıt yapılmadı.');\n    el.focus();\n    return;\n  }\n  if(!confirm(scna+' için şoföre verilen toplam nakit '+money(amount)+' IQD olarak kaydedilsin mi?'))return;"""
if old_func not in s:
    raise RuntimeError('saveMissingExitCash function anchor not found')
s=s.replace(old_func,new_func,1)

p.write_text(s,encoding='utf-8')
print('patched exit cash overpayment validation v3')
