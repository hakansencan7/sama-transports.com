from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_EXIT_CASH_SUMMARY_V4'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

old='''    <div>Çıkış Mazot Maliyeti<strong id="xFuelCost">0</strong></div>\n  </div>'''
new='''    <div>Çıkış Mazot Maliyeti<strong id="xFuelCost">0</strong></div>\n    <div style="border:2px solid #2563eb;background:#eff6ff">Şoföre Verilmesi Gereken<strong id="xRequiredCash">0 IQD</strong><span class="small">Mazot + Harcırah + Prim + Dock + Port + SONAR + OTHER</span></div>\n    <div id="xCashDiffBox" style="border:2px solid #cbd5e1"><span id="xCashDiffLabel">Girilen Para Kontrolü</span><strong id="xCashDiff">0 IQD</strong></div>\n  </div>\n  '''+MARK
if old not in s:
    raise RuntimeError('exit settle anchor not found')
s=s.replace(old,new,1)

# Recalculate whenever cash/expense inputs change.
repls={
'id="xCash" type="text" inputmode="decimal" value="${cx.exit_cash||0}"':'id="xCash" type="text" inputmode="decimal" value="${cx.exit_cash||0}" oninput="calcExitFuel()"',
'id="xAllow" type="text" inputmode="decimal" value="${cx.exit_allowance||0}"':'id="xAllow" type="text" inputmode="decimal" value="${cx.exit_allowance||0}" oninput="calcExitFuel()"',
'id="xOther" type="text" inputmode="decimal" value="${cx.exit_other||0}"':'id="xOther" type="text" inputmode="decimal" value="${cx.exit_other||0}" oninput="calcExitFuel()"'
}
for a,b in repls.items():
    if a not in s: raise RuntimeError('input anchor not found: '+a[:30])
    s=s.replace(a,b,1)

old_calc='''  xFuelCost.innerText=money(fuelCost);\n}'''
new_calc='''  xFuelCost.innerText=money(fuelCost);\n\n  // Şoföre çıkışta fiilen verilmesi gereken toplam nakit.\n  // Resmi/ticari/Bağdat mazot tutarları bu iş akışında şoföre verilen nakdin parçasıdır.\n  const requiredCash=\n    fuelCost+\n    Number(cx.exit_premium||0)+\n    Number(cx.dock_fee||0)+\n    Number(cx.port_fee||0)+\n    Number(cx.sonar||0)+\n    parseMoney(xAllow.value)+\n    parseMoney(xOther.value);\n  const enteredCash=parseMoney(xCash.value);\n  const cashDiff=enteredCash-requiredCash;\n  if(document.getElementById('xRequiredCash')) xRequiredCash.innerText=money(requiredCash)+' IQD';\n  if(document.getElementById('xCashDiff')) xCashDiff.innerText=money(Math.abs(cashDiff))+' IQD';\n  if(document.getElementById('xCashDiffLabel')){\n    if(cashDiff>0.01){xCashDiffLabel.innerText='FAZLA PARA';xCashDiffBox.style.borderColor='#ef4444';xCashDiffBox.style.background='#fef2f2';xCashDiff.style.color='#b91c1c';}\n    else if(cashDiff < -0.01){xCashDiffLabel.innerText='EKSİK PARA';xCashDiffBox.style.borderColor='#f59e0b';xCashDiffBox.style.background='#fffbeb';xCashDiff.style.color='#b45309';}\n    else{xCashDiffLabel.innerText='PARA TAMAM';xCashDiffBox.style.borderColor='#22c55e';xCashDiffBox.style.background='#f0fdf4';xCashDiff.style.color='#166534';}\n  }\n}\n'''
if old_calc not in s: raise RuntimeError('calc anchor not found')
s=s.replace(old_calc,new_calc,1)

# Block save in the main exit modal too, not only the missing-cash repair screen.
old_save='''    try{\n      if(parseMoney(xOther.value)>0 && !(document.getElementById('xOtherNote')?.value||'').trim()){alert('OTHER tutarı için açıklama zorunlu.');return;}\n      await api('/api/trips/'+scna+'/exit',{'''
new_save='''    try{\n      if(parseMoney(xOther.value)>0 && !(document.getElementById('xOtherNote')?.value||'').trim()){alert('OTHER tutarı için açıklama zorunlu.');return;}\n      const requiredCash=parseMoney(xOffTotal.value)+parseMoney(xComTotal.value)+parseMoney(xBagTotal.value)+parseMoney(xAllow.value)+Number(cx.exit_premium||0)+Number(cx.dock_fee||0)+Number(cx.port_fee||0)+Number(cx.sonar||0)+parseMoney(xOther.value);\n      const enteredCash=parseMoney(xCash.value);\n      if(enteredCash>requiredCash+0.01){\n        alert('HATA: Fazla para girdiniz.\\n\\nŞoföre verilmesi gereken: '+money(requiredCash)+' IQD\\nGirilen: '+money(enteredCash)+' IQD\\nFazla: '+money(enteredCash-requiredCash)+' IQD\\n\\nKayıt yapılmadı.');\n        xCash.focus(); return;\n      }\n      await api('/api/trips/'+scna+'/exit',{'''
if old_save not in s: raise RuntimeError('exit save anchor not found')
s=s.replace(old_save,new_save,1)

p.write_text(s,encoding='utf-8')
print('patched exit cash summary v4')
