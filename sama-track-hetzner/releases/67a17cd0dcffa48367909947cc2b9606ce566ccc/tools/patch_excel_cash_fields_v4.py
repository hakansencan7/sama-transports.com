from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_EXCEL_CASH_FIELDS_V4'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

# 1) Read cash fields after collection is parsed.
anchor='''                # AW = COLLECTION = müşteriden fiilen alınan para.\n                collection=_excel_num(row[48] if len(row)>48 else _first(row,header_map,["COLLECTION","Tahsilat","Müşteriden Alınan Para"],0))\n'''
replacement='''                # AW = COLLECTION = müşteriden fiilen alınan para.\n                collection=_excel_num(row[48] if len(row)>48 else _first(row,header_map,["COLLECTION","Tahsilat","Müşteriden Alınan Para"],0))\n\n                # SAMA_EXCEL_CASH_FIELDS_V4\n                # Muhasebe için COLLECTION ile şoförün fiilen teslim ettiği para aynı şey değildir.\n                # Bu yüzden yalnızca açıkça isimlendirilmiş Excel alanlarını entry_cash_handed olarak okuruz.\n                entry_cash_handed=_excel_num(_first(row,header_map,[\n                    "Şoförün Teslim Ettiği Para","Soforun Teslim Ettigi Para",\n                    "Şoförün Verdiği Para","Soforun Verdigi Para",\n                    "Entry Cash Handed","Cash Handed","Driver Cash Handed",\n                    "Teslim Edilen Para","Kasa Teslim"\n                ],0))\n\n                # Çıkışta şoföre verilen toplam nakit. Yeni/ayrıntılı Excel başlıkları önceliklidir.\n                exit_cash=_excel_num(_first(row,header_map,[\n                    "Şoföre Verilen Avans","Sofore Verilen Avans",\n                    "Şoföre Verilen Para","Sofore Verilen Para",\n                    "Exit Cash","Driver Cash","Cash Given To Driver"\n                ],0))\n\n                # Eski YUKLEME LISTESI'nde X sütunu 'Driver' para alanı olarak kullanılıyordu.\n                # Başlıkla açık bir exit_cash bulunmadıysa yalnızca bu eski sabit kolonu fallback olarak kullan.\n                if not exit_cash and len(row)>23:\n                    exit_cash=_excel_num(row[23])\n'''
if anchor not in s:
    raise RuntimeError('cash parse anchor not found')
s=s.replace(anchor,replacement,1)

# 2) Add preview fields.
anchor='''                    "collection":collection,\n                    "excel_remain":excel_remain,\n'''
replacement='''                    "collection":collection,\n                    "entry_cash_handed":entry_cash_handed,\n                    "exit_cash":exit_cash,\n                    "excel_remain":excel_remain,\n'''
if anchor not in s:
    raise RuntimeError('preview anchor not found')
s=s.replace(anchor,replacement,1)

# 3) Existing row UPDATE: add exit_cash and entry_cash_handed columns.
anchor='''                        exit_km=?,\n                        tank_start_liters=?,\n'''
replacement='''                        exit_km=?,\n                        exit_cash=?,\n                        tank_start_liters=?,\n'''
if anchor not in s:
    raise RuntimeError('update exit anchor not found')
s=s.replace(anchor,replacement,1)

anchor='''                        entry_collection=?,\n                        excel_price_k=?,\n'''
replacement='''                        entry_collection=?,\n                        entry_cash_handed=CASE WHEN ?>0 THEN ? ELSE entry_cash_handed END,\n                        excel_price_k=?,\n'''
if anchor not in s:
    raise RuntimeError('update entry anchor not found')
s=s.replace(anchor,replacement,1)

anchor='''                        net_kg,freight_rate,freight_basis,\n                        exit_km,tank_start,off_lt,off_total,\n'''
replacement='''                        net_kg,freight_rate,freight_basis,\n                        exit_km,exit_cash,tank_start,off_lt,off_total,\n'''
if anchor not in s:
    raise RuntimeError('update values exit anchor not found')
s=s.replace(anchor,replacement,1)

anchor='''                        entry_km,tank_end,collection,price_k,freight_rate_au,freight_total,excel_remain,delivery_time,\n'''
replacement='''                        entry_km,tank_end,collection,entry_cash_handed,entry_cash_handed,price_k,freight_rate_au,freight_total,excel_remain,delivery_time,\n'''
if anchor not in s:
    raise RuntimeError('update values entry anchor not found')
s=s.replace(anchor,replacement,1)

# 4) INSERT columns and values.
anchor='''                      exit_km,tank_start_liters,exit_official_fuel_liters,exit_official_fuel_total,\n'''
replacement='''                      exit_km,exit_cash,tank_start_liters,exit_official_fuel_liters,exit_official_fuel_total,\n'''
if anchor not in s:
    raise RuntimeError('insert exit columns anchor not found')
s=s.replace(anchor,replacement,1)

anchor='''                      entry_km,tank_end_liters,entry_collection,excel_price_k,excel_freight_au,excel_amount,excel_remain,delivery_time,\n'''
replacement='''                      entry_km,tank_end_liters,entry_collection,entry_cash_handed,excel_price_k,excel_freight_au,excel_amount,excel_remain,delivery_time,\n'''
if anchor not in s:
    raise RuntimeError('insert entry columns anchor not found')
s=s.replace(anchor,replacement,1)

# Update placeholder count automatically for this one INSERT statement.
old='''                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)\n'''
new='''                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)\n'''
if old not in s:
    raise RuntimeError('insert placeholders anchor not found')
s=s.replace(old,new,1)

anchor='''                    net_kg,freight_rate,freight_basis,\n                    exit_km,tank_start,off_lt,off_total,\n'''
replacement='''                    net_kg,freight_rate,freight_basis,\n                    exit_km,exit_cash,tank_start,off_lt,off_total,\n'''
if anchor not in s:
    raise RuntimeError('insert values exit anchor not found')
s=s.replace(anchor,replacement,1)

anchor='''                    entry_km,tank_end,collection,price_k,freight_rate_au,freight_total,excel_remain,delivery_time,\n'''
replacement='''                    entry_km,tank_end,collection,entry_cash_handed,price_k,freight_rate_au,freight_total,excel_remain,delivery_time,\n'''
if anchor not in s:
    raise RuntimeError('insert values entry anchor not found')
s=s.replace(anchor,replacement,1)

p.write_text(s,encoding='utf-8')
print('patched Excel cash fields v4')
