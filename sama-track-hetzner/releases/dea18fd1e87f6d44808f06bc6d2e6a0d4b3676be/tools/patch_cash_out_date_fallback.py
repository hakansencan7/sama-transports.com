from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_CASH_OUT_DATE_FALLBACK_V2'
if MARK in s:
    print('already patched')
    raise SystemExit(0)
old='''    # SAMA_SHIPMENT_CASH_OUT_V1\n    # Sevkiyat cikisinda sofore fiilen verilen para (trips.exit_cash) kasadan cikistir.\n    # Sevkiyat tablosu burada sadece okunur; kasa modulu trips kaydini degistirmez.\n    shipment_out_rows=[]\n    if cur=='IQD':\n        shipment_out_rows=[dict(r) for r in c.execute(\"\"\"\n          SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name,\n                 t.exit_cash amount,t.exit_at exit_date\n          FROM trips t\n          LEFT JOIN drivers d ON d.id=t.driver_id\n          WHERE t.exit_done=1\n            AND COALESCE(t.is_deleted,0)=0\n            AND COALESCE(t.exit_cash,0)>0\n            AND DATE(t.exit_at)=?\n          ORDER BY t.exit_at DESC,t.scna\n        \"\"\",(day,))]\n'''
new='''    # SAMA_SHIPMENT_CASH_OUT_V1\n    # SAMA_CASH_OUT_DATE_FALLBACK_V2\n    # Sevkiyat cikisinda sofore fiilen verilen para (trips.exit_cash) kasadan cikistir.\n    # Eski kayitlarda exit_at bos olabildigi icin efektif cikis tarihi sirayla\n    # exit_at -> trip_date -> created_at alanlarindan okunur. Sevkiyat tablosu salt okunurdur.\n    shipment_out_rows=[]\n    if cur=='IQD':\n        shipment_out_rows=[dict(r) for r in c.execute(\"\"\"\n          SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name,\n                 t.exit_cash amount,\n                 COALESCE(NULLIF(t.exit_at,''),NULLIF(t.trip_date,''),NULLIF(t.created_at,'')) exit_date\n          FROM trips t\n          LEFT JOIN drivers d ON d.id=t.driver_id\n          WHERE t.exit_done=1\n            AND COALESCE(t.is_deleted,0)=0\n            AND COALESCE(t.exit_cash,0)>0\n            AND DATE(COALESCE(NULLIF(t.exit_at,''),NULLIF(t.trip_date,''),NULLIF(t.created_at,'')))=?\n          ORDER BY COALESCE(NULLIF(t.exit_at,''),NULLIF(t.trip_date,''),NULLIF(t.created_at,'')) DESC,t.scna\n        \"\"\",(day,))]\n'''
if old not in s:
    raise RuntimeError('cash out query anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('patched cash out date fallback')
