from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_EXIT_CASH_MISSING_EXPENSES_V2'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

s=s.replace("# SAMA_EXIT_CASH_MISSING_FROM_20260830_V1", "# SAMA_EXIT_CASH_MISSING_FROM_20260830_V1\n# SAMA_EXIT_CASH_MISSING_EXPENSES_V2", 1)

old="""             t.trip_date,t.exit_at,t.created_at,t.exit_allowance,t.exit_premium,t.exit_other,\n             t.exit_cash,t.exit_done,t.status"""
new="""             t.trip_date,t.exit_at,t.created_at,t.exit_allowance,t.exit_premium,t.exit_other,\n             t.exit_official_fuel_total,t.exit_commercial_fuel_total,t.exit_baghdad_fuel_total,\n             t.dock_fee,t.port_fee,t.sonar,\n             (COALESCE(t.exit_official_fuel_total,0)+COALESCE(t.exit_commercial_fuel_total,0)+COALESCE(t.exit_baghdad_fuel_total,0)) fuel_total,\n             (COALESCE(t.exit_allowance,0)+COALESCE(t.exit_premium,0)+COALESCE(t.exit_other,0)+COALESCE(t.dock_fee,0)+COALESCE(t.port_fee,0)+COALESCE(t.sonar,0)+\n              COALESCE(t.exit_official_fuel_total,0)+COALESCE(t.exit_commercial_fuel_total,0)+COALESCE(t.exit_baghdad_fuel_total,0)) visible_expense_total,\n             t.exit_cash,t.exit_done,t.status"""
if old not in s:
    raise RuntimeError('backend select anchor not found')
s=s.replace(old,new,1)

old_head='<th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>ÇIKIŞ TARİHİ</th><th>HARCIRAH</th><th>PRİM</th><th>OTHER</th><th>ŞOFÖRE VERİLEN TOPLAM NAKİT</th><th>İŞLEM</th>'
new_head='<th>SCNA</th><th>PLAKA</th><th>ŞOFÖR</th><th>ÇIKIŞ TARİHİ</th><th>RESMİ MAZOT</th><th>TİCARİ MAZOT</th><th>BAĞDAT MAZOT</th><th>MAZOT TOPLAM</th><th>HARCIRAH</th><th>PRİM</th><th>OTHER</th><th>DOCK</th><th>PORT</th><th>SONAR</th><th>GÖRÜNEN GİDER TOPLAMI</th><th>ŞOFÖRE VERİLEN TOPLAM NAKİT</th><th>İŞLEM</th>'
if old_head not in s:
    raise RuntimeError('table head anchor not found')
s=s.replace(old_head,new_head,1)

old_row="""<td><b>${x.scna}</b></td><td>${x.plate||''}</td><td>${x.driver_name||''}</td><td>${fmtDateTime(x.exit_at||x.trip_date||x.created_at)}</td><td>${money(x.exit_allowance||0)}</td><td>${money(x.exit_premium||0)}</td><td>${money(x.exit_other||0)}</td><td><input id=\"missingCash_${String(x.scna).replace(/[^A-Za-z0-9_]/g,'_')}\" type=\"text\" inputmode=\"decimal\" placeholder=\"Toplam IQD\" style=\"width:150px\"></td><td><button class=\"btn orange\" onclick=\"saveMissingExitCash('${String(x.scna).replace(/'/g,\"\\\\'\")}')\">Kaydet</button></td>"""
new_row="""<td><b>${x.scna}</b></td><td>${x.plate||''}</td><td>${x.driver_name||''}</td><td>${fmtDateTime(x.exit_at||x.trip_date||x.created_at)}</td><td>${money(x.exit_official_fuel_total||0)}</td><td>${money(x.exit_commercial_fuel_total||0)}</td><td>${money(x.exit_baghdad_fuel_total||0)}</td><td><b>${money(x.fuel_total||0)}</b></td><td>${money(x.exit_allowance||0)}</td><td>${money(x.exit_premium||0)}</td><td>${money(x.exit_other||0)}</td><td>${money(x.dock_fee||0)}</td><td>${money(x.port_fee||0)}</td><td>${money(x.sonar||0)}</td><td><b>${money(x.visible_expense_total||0)}</b></td><td><input id=\"missingCash_${String(x.scna).replace(/[^A-Za-z0-9_]/g,'_')}\" type=\"text\" inputmode=\"decimal\" placeholder=\"Toplam IQD\" style=\"width:150px\"></td><td><button class=\"btn orange\" onclick=\"saveMissingExitCash('${String(x.scna).replace(/'/g,\"\\\\'\")}')\">Kaydet</button></td>"""
if old_row not in s:
    raise RuntimeError('table row anchor not found')
s=s.replace(old_row,new_row,1)

p.write_text(s,encoding='utf-8')
print('patched missing exit cash expense details v2')
