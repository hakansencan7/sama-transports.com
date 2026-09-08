from pathlib import Path

p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_ENTRY_CASH_DATE_FALLBACK_V2'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

old_query="""          SELECT scna,plate,entry_cash_handed amount,entry_at entry_date
          FROM trips
          WHERE entry_done=1
            AND COALESCE(is_deleted,0)=0
            AND COALESCE(entry_cash_handed,0)>0
            AND DATE(entry_at)=?
          ORDER BY entry_at DESC,scna
"""
new_query="""          SELECT scna,plate,entry_cash_handed amount,
                 COALESCE(NULLIF(entry_at,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')) entry_date
          FROM trips
          WHERE entry_done=1
            AND COALESCE(is_deleted,0)=0
            AND COALESCE(entry_cash_handed,0)>0
            AND DATE(COALESCE(NULLIF(entry_at,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')))=?
          ORDER BY COALESCE(NULLIF(entry_at,''),NULLIF(updated_at,''),NULLIF(trip_date,''),NULLIF(created_at,'')) DESC,scna
"""
if old_query not in s:
    raise RuntimeError('cash-control entry query anchor not found')
s=s.replace(old_query,new_query,1)

old_select="""             t.entry_done,t.entry_cash_handed,t.entry_collection,t.entry_at,
             t.delivery_time,t.trip_date,t.created_at,t.status,COALESCE(t.is_deleted,0) is_deleted
"""
new_select="""             t.entry_done,t.entry_cash_handed,t.entry_collection,t.entry_at,
             t.delivery_time,t.trip_date,t.created_at,t.updated_at,t.status,COALESCE(t.is_deleted,0) is_deleted
"""
if old_select not in s:
    raise RuntimeError('diagnostic select anchor not found')
s=s.replace(old_select,new_select,1)

old_logic="""    effective_entry=x.get('entry_at') or x.get('delivery_time') or None
    reasons=[]
    if int(x.get('is_deleted') or 0)!=0: reasons.append('Kayıt silinmiş')
    if int(x.get('entry_done') or 0)!=1: reasons.append('Giriş işlemi tamamlanmamış (entry_done != 1)')
    if float(x.get('entry_cash_handed') or 0)<=0: reasons.append('Şoförün Teslim Ettiği Para 0 veya boş')
    if not x.get('entry_at'): reasons.append('entry_at boş. Günlük Kasa DATE(entry_at) kullandığı için muhasebeye düşmez')
    eligible=(len(reasons)==0)
"""
new_logic="""    effective_entry=x.get('entry_at') or x.get('updated_at') or x.get('trip_date') or x.get('created_at') or None
    reasons=[]
    if int(x.get('is_deleted') or 0)!=0: reasons.append('Kayıt silinmiş')
    if int(x.get('entry_done') or 0)!=1: reasons.append('Giriş işlemi tamamlanmamış (entry_done != 1)')
    if float(x.get('entry_cash_handed') or 0)<=0: reasons.append('Şoförün Teslim Ettiği Para 0 veya boş')
    if not effective_entry: reasons.append('Giriş tarihi bulunamadı')
    eligible=(len(reasons)==0)
"""
if old_logic not in s:
    raise RuntimeError('diagnostic logic anchor not found')
s=s.replace(old_logic,new_logic,1)

ui_old="""<tr><th>entry_at</th><td>${fmtDateTime(x.entry_at)}</td></tr><tr><th>delivery_time</th><td>${fmtDateTime(x.delivery_time)}</td></tr><tr><th>trip_date</th><td>${x.trip_date||''}</td></tr><tr><th>created_at</th><td>${fmtDateTime(x.created_at)}</td></tr>"""
ui_new="""<tr><th>entry_at</th><td>${fmtDateTime(x.entry_at)}</td></tr><tr><th>updated_at</th><td>${fmtDateTime(x.updated_at)}</td></tr><tr><th>Efektif Muhasebe Tarihi</th><td><b>${fmtDateTime(x.effective_entry_date)}</b></td></tr><tr><th>delivery_time</th><td>${fmtDateTime(x.delivery_time)}</td></tr><tr><th>trip_date</th><td>${x.trip_date||''}</td></tr><tr><th>created_at</th><td>${fmtDateTime(x.created_at)}</td></tr>"""
if ui_old not in s:
    raise RuntimeError('diagnostic ui anchor not found')
s=s.replace(ui_old,ui_new,1)

insert_anchor='# SAMA_ENTRY_CASH_DIAGNOSTIC_V1\n'
s=s.replace(insert_anchor,insert_anchor+MARK+'\n',1)

p.write_text(s,encoding='utf-8')
print('patched entry cash date fallback v2')
