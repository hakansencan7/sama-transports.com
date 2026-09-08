from pathlib import Path
p=Path('app.py'); s=p.read_text(encoding='utf-8')
MARK='# SAMA_ADVANCE_SIGNED_BALANCE_V2'
if MARK in s: print('already patched'); raise SystemExit
s=s.replace('# SAMA_ADVANCE_PERSON_ACCOUNTS_V1','# SAMA_ADVANCE_PERSON_ACCOUNTS_V1\n'+MARK,1)
s=s.replace("ROUND(SUM(MAX(amount-settled_amount,0)),2) open_balance,", "ROUND(SUM(amount-settled_amount),2) open_balance,",1)
s=s.replace("SELECT a.*,MAX(0,a.amount-a.settled_amount) remaining FROM cash_advances a", "SELECT a.*,(a.amount-a.settled_amount) remaining FROM cash_advances a",1)
s=s.replace("'open_balance':max(0,total-settled)", "'open_balance':total-settled",1)
# allow bulk/single settlements to exceed an individual advance so the person account can become creditor
old="if newsettled > float(a['amount'] or 0) + 0.0001: raise HTTPException(400,'Kapatma toplamı avans tutarını aşamaz.')"
if old in s: s=s.replace(old,"# Signed person account: settlement may exceed this advance; excess becomes company debt to person.",1)
# update edit endpoint over-settlement guard if present
old2="if newsettled > float(a['amount'] or 0) + 0.0001:\n        c.close(); raise HTTPException(400,'Kapatma toplamı avans tutarını aşamaz.')"
if old2 in s: s=s.replace(old2,"# Signed person account: excess settlement is allowed and appears as negative person balance.",1)
# statuses: over-settled still closed at advance level
# person offset: signed balance; if negative, company owes person and cash requirement increases
old3="available=sum(max(0,float(a['amount'] or 0)-float(a['settled_amount'] or 0)) for a in olds)\n    offset=min(need,available); left=offset"
new3="available=sum(max(0,float(a['amount'] or 0)-float(a['settled_amount'] or 0)) for a in olds)\n    person_net=sum(float(r[0] or 0)-float(r[1] or 0) for r in c.execute(\"SELECT amount,settled_amount FROM cash_advances WHERE recipient_type=? AND UPPER(TRIM(recipient_name))=UPPER(TRIM(?)) AND currency=?\",(typ,name,cur)))\n    company_debt=max(0,-person_net)\n    offset=min(need,max(0,person_net))\n    left=offset"
if old3 not in s: raise SystemExit('offset calc anchor not found')
s=s.replace(old3,new3,1)
s=s.replace("cash_to_give=max(0,need-offset); new_id=None", "cash_to_give=max(0,need-offset+company_debt); new_id=None",1)
s=s.replace("return {'ok':True,'new_need':need,'offset':offset,'cash_to_give':cash_to_give,'new_advance_id':new_id}", "return {'ok':True,'new_need':need,'offset':offset,'company_debt':company_debt,'cash_to_give':cash_to_give,'new_advance_id':new_id}",1)
# UI terminology and signed math
s=s.replace("<th>AÇIK BAKİYE</th>","<th>CARİ BAKİYE</th>",1)
s=s.replace("<b>Açık Bakiye:</b> ${money(x.open_balance)}", "<b>Cari Bakiye:</b> ${money(x.open_balance)} <span class=\"small\">(+ kişi şirkete borçlu / - şirket kişiye borçlu)</span>",1)
s=s.replace("<b>Mevcut açık bakiye:</b> ${money(x.open_balance)} ${x.currency}", "<b>Mevcut cari bakiye:</b> ${money(x.open_balance)} ${x.currency}<br><span class=\"small\">Pozitif: kişinin elinde şirket parası. Negatif: şirket kişiye borçlu.</span>",1)
oldjs="const x=window._advancePersonCurrent||{},need=Number(document.getElementById('apoNeed')?.value||0),off=Math.min(need,Number(x.open_balance||0)),cash=Math.max(0,need-off);"
newjs="const x=window._advancePersonCurrent||{},need=Number(document.getElementById('apoNeed')?.value||0),bal=Number(x.open_balance||0),off=Math.min(need,Math.max(0,bal)),debt=Math.max(0,-bal),cash=Math.max(0,need-off+debt);"
if oldjs not in s: raise SystemExit('ui calc anchor not found')
s=s.replace(oldjs,newjs,1)
oldsave="const need=Number(apoNeed.value||0),off=Math.min(need,Number(x.open_balance||0)),cash=Math.max(0,need-off);"
newsave="const need=Number(apoNeed.value||0),bal=Number(x.open_balance||0),off=Math.min(need,Math.max(0,bal)),debt=Math.max(0,-bal),cash=Math.max(0,need-off+debt);"
if oldsave in s: s=s.replace(oldsave,newsave,1)
p.write_text(s,encoding='utf-8'); print('patched signed balance')
