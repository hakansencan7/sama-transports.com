from pathlib import Path
p=Path('app.py'); s=p.read_text(encoding='utf-8')
MARK='# SAMA_ADVANCE_SIGNED_BALANCE_V3'
if MARK in s: print('already patched'); raise SystemExit
anchor='# SAMA_ADVANCE_SIGNED_BALANCE_V2'
if anchor in s: s=s.replace(anchor,anchor+'\n'+MARK,1)
else: s=s.replace('# SAMA_ADVANCE_PERSON_ACCOUNTS_V1','# SAMA_ADVANCE_PERSON_ACCOUNTS_V1\n'+MARK,1)
# list must expose signed balance per advance
s=s.replace("SELECT a.*,MAX(0,a.amount-a.settled_amount) remaining\n      FROM cash_advances a WHERE 1=1", "SELECT a.*,(a.amount-a.settled_amount) remaining\n      FROM cash_advances a WHERE 1=1",1)
# normal settlement: allow invoices/receipts/returns to exceed one advance; the excess is company debt to person
old="""    remaining=max(0,float(row['amount'] or 0)-float(row['settled_amount'] or 0))
    if amt>remaining+0.0001: c.close(); raise HTTPException(400,f'Girilen tutar kalan avansı aşamaz. Kalan: {remaining:g}')
"""
if old in s: s=s.replace(old,"    remaining=float(row['amount'] or 0)-float(row['settled_amount'] or 0)\n",1)
s=s.replace("return {'ok':True,'status':status,'settled_amount':newsettled,'remaining':max(0,float(row['amount'] or 0)-newsettled)}", "return {'ok':True,'status':status,'settled_amount':newsettled,'remaining':float(row['amount'] or 0)-newsettled}",1)
# editing original advance amount may place person account negative
s=s.replace("    if amount < float(row['settled_amount'] or 0): c.close(); raise HTTPException(400,'Yeni tutar belgelenmiş/iadeli tutardan küçük olamaz.')\n", "",1)
# correction of existing settlement may also exceed original advance
old2="""    if newsettled>advance_amount+0.0001:
        c.close(); raise HTTPException(400,f'Düzeltilen tutarla toplam belgelenen avansı aşamaz. Avans: {advance_amount:g} / Toplam: {newsettled:g}')
"""
if old2 in s: s=s.replace(old2,"",1)
s=s.replace("return {'ok':True,'status':status,'settled_amount':newsettled,'remaining':max(0,advance_amount-newsettled)}", "return {'ok':True,'status':status,'settled_amount':newsettled,'remaining':advance_amount-newsettled}",1)
# status remains KAPANDI for zero or negative record-level balance; person ledger shows the signed debt.
p.write_text(s,encoding='utf-8'); print('patched signed balance v3')
