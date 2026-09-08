from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_EXCEL_EXIT_CASH_FIX_V5'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

old='''                # Eski YUKLEME LISTESI'nde X sütunu 'Driver' para alanı olarak kullanılıyordu.\n                # Başlıkla açık bir exit_cash bulunmadıysa yalnızca bu eski sabit kolonu fallback olarak kullan.\n                if not exit_cash and len(row)>23:\n                    exit_cash=_excel_num(row[23])\n'''
new='''                # SAMA_EXCEL_EXIT_CASH_FIX_V5\n                # X sütunu (Driver) toplam kasa çıkışı değildir. Eski dosyada sürücü masraf alanıdır;\n                # bu yüzden artık exit_cash için kullanılmaz. Açık bir nakit kolonu yoksa, kullanıcı\n                # kuralına göre şoföre verilen toplam nakit görünür çıkış giderlerinin toplamıdır.\n                if not exit_cash:\n                    exit_cash=(\n                        off_total+com_total+bag_total+allowance+premium+other+\n                        dock_fee+port_fee+sonar\n                    )\n'''
if old not in s:
    raise RuntimeError('old X-column exit_cash fallback not found')
s=s.replace(old,new,1)

# One-time conservative repair for records affected by V4 on/after 2026-08-30.
# Only touch rows where exit_cash exactly equals allowance while visible expenses are higher.
anchor='''@app.get('/api/exit-cash-missing')\ndef exit_cash_missing():\n'''
repair='''def _repair_v4_exit_cash_misimports():\n    c=db()\n    rows=c.execute("""\n      SELECT id,scna,exit_cash,exit_allowance,\n             (COALESCE(exit_official_fuel_total,0)+COALESCE(exit_commercial_fuel_total,0)+\n              COALESCE(exit_baghdad_fuel_total,0)+COALESCE(exit_allowance,0)+\n              COALESCE(exit_premium,0)+COALESCE(exit_other,0)+COALESCE(dock_fee,0)+\n              COALESCE(port_fee,0)+COALESCE(sonar,0)) expected_cash\n      FROM trips\n      WHERE COALESCE(is_deleted,0)=0\n        AND exit_done=1\n        AND DATE(COALESCE(NULLIF(exit_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')))>=DATE('2026-08-30')\n        AND COALESCE(exit_cash,0)>0\n        AND ABS(COALESCE(exit_cash,0)-COALESCE(exit_allowance,0))<0.01\n    """).fetchall()\n    fixed=[]\n    for r in rows:\n        expected=float(r['expected_cash'] or 0)\n        current=float(r['exit_cash'] or 0)\n        if expected>current+0.01:\n            c.execute("UPDATE trips SET exit_cash=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(expected,r['id']))\n            fixed.append((r['scna'],current,expected))\n    c.commit(); c.close()\n    return fixed\n\n'''+anchor
if anchor not in s:
    raise RuntimeError('exit cash missing anchor not found')
s=s.replace(anchor,repair,1)

# Run repair after database init/startup. Keep it idempotent by condition.
anchor='''def startup():\n    prepare_database_file()\n    init_db()\n'''
replacement='''def startup():\n    prepare_database_file()\n    init_db()\n    try:\n        fixed=_repair_v4_exit_cash_misimports()\n        if fixed:\n            print(f'SAMA_EXCEL_EXIT_CASH_FIX_V5 repaired {len(fixed)} rows')\n    except Exception as e:\n        print('SAMA_EXCEL_EXIT_CASH_FIX_V5 repair warning:',e)\n'''
if anchor not in s:
    raise RuntimeError('startup anchor not found')
s=s.replace(anchor,replacement,1)

p.write_text(s,encoding='utf-8')
print('patched Excel exit cash fix v5')
