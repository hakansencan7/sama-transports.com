from pathlib import Path
p=Path('app.py'); s=p.read_text(encoding='utf-8')
MARK='# SAMA_SHIPMENT_CASH_OUT_V1'
if MARK in s:
 print('already patched'); raise SystemExit(0)

needle="    shipment_cash_in=sum(float(r['amount'] or 0) for r in shipment_rows)\n    advances=float(c.execute(\"SELECT COALESCE(SUM(amount),0) FROM cash_advances WHERE currency=? AND DATE(created_at)=?\",(cur,day)).fetchone()[0] or 0)"
repl="""    shipment_cash_in=sum(float(r['amount'] or 0) for r in shipment_rows)
    # SAMA_SHIPMENT_CASH_OUT_V1
    # Sevkiyat cikisinda sofore fiilen verilen para (trips.exit_cash) kasadan cikistir.
    # Sevkiyat tablosu burada sadece okunur; kasa modulu trips kaydini degistirmez.
    shipment_out_rows=[]
    if cur=='IQD':
        shipment_out_rows=[dict(r) for r in c.execute(\"\"\"
          SELECT t.scna,t.plate,COALESCE(d.name,'') driver_name,
                 t.exit_cash amount,t.exit_at exit_date
          FROM trips t
          LEFT JOIN drivers d ON d.id=t.driver_id
          WHERE t.exit_done=1
            AND COALESCE(t.is_deleted,0)=0
            AND COALESCE(t.exit_cash,0)>0
            AND DATE(t.exit_at)=?
          ORDER BY t.exit_at DESC,t.scna
        \"\"\",(day,))]
    shipment_cash_out=sum(float(r['amount'] or 0) for r in shipment_out_rows)
    advances=float(c.execute(\"SELECT COALESCE(SUM(amount),0) FROM cash_advances WHERE currency=? AND DATE(created_at)=?\",(cur,day)).fetchone()[0] or 0)"""
if needle not in s: raise RuntimeError('backend cash anchor missing')
s=s.replace(needle,repl,1)

old="expected=opening+shipment_cash_in+other_cash_in-advances-expenses; diff=actual-expected"
new="expected=opening+shipment_cash_in+other_cash_in-shipment_cash_out-advances-expenses; diff=actual-expected"
if old not in s: raise RuntimeError('expected formula anchor missing')
s=s.replace(old,new,1)

old="'shipment_cash_in':shipment_cash_in,'shipment_cash_entries':shipment_rows,\n      'other_cash_in':other_cash_in,'cash_in':other_cash_in,"
new="'shipment_cash_in':shipment_cash_in,'shipment_cash_entries':shipment_rows,\n      'shipment_cash_out':shipment_cash_out,'shipment_cash_out_entries':shipment_out_rows,\n      'other_cash_in':other_cash_in,'cash_in':other_cash_in,"
if old not in s: raise RuntimeError('return anchor missing')
s=s.replace(old,new,1)

card='<div class="card">Verilen Avans<b id="cashAdvance">0</b></div>'
newcard='<div class="card" role="button" tabindex="0" style="cursor:pointer" onclick="openShipmentCashOutDetails()">Sevkiyat Çıkışı / Şoföre Verilen ↗<b id="cashShipmentOut">0</b></div>'+card
if card not in s: raise RuntimeError('cash card anchor missing')
s=s.replace(card,newcard,1)

oldnote='Beklenen Kasa = Gün Başı Kasa + Sevkiyattan Gelen + Diğer Kasa Girişi − Avanslar − Günlük Doğrudan Harcamalar. Sevkiyattan Gelen kartına tıklayarak SCNA detaylarını görebilirsiniz.'
newnote='Beklenen Kasa = Gün Başı Kasa + Sevkiyattan Gelen + Diğer Kasa Girişi − Sevkiyat Çıkışında Şoföre Verilen − Avanslar − Günlük Doğrudan Harcamalar. Sevkiyat giriş/çıkış kartlarına tıklayarak SCNA detaylarını görebilirsiniz.'
if oldnote not in s: raise RuntimeError('cash note anchor missing')
s=s.replace(oldnote,newnote,1)

oldjs="cashShipmentIn.innerText=money(cashSummary.shipment_cash_in)+' '+c; cashIn.innerText=money(cashSummary.other_cash_in)+' '+c; cashAdvance.innerText=money(cashSummary.advance_out)+' '+c;"
newjs="cashShipmentIn.innerText=money(cashSummary.shipment_cash_in)+' '+c; cashIn.innerText=money(cashSummary.other_cash_in)+' '+c; cashShipmentOut.innerText=money(cashSummary.shipment_cash_out||0)+' '+c; cashAdvance.innerText=money(cashSummary.advance_out)+' '+c;"
if oldjs not in s: raise RuntimeError('cash JS summary anchor missing')
s=s.replace(oldjs,newjs,1)

fn="""function openShipmentCashOutDetails(){
 const x=cashSummary||{},rows=x.shipment_cash_out_entries||[],cur=x.currency||cashCur.value;
 const body=rows.length?rows.map(r=>`<tr><td><b>${r.scna||''}</b></td><td>${r.plate||''}</td><td>${r.driver_name||''}</td><td>${money(r.amount)} ${cur}</td><td>${fmtDateTime(r.exit_date)}</td></tr>`).join(''):`<tr><td colspan="5" class="muted">Bu tarihte sevkiyat cikisinda sofore verilen para yok.</td></tr>`;
 openM('Sevkiyat Çıkışı / Şoföre Verilen',`<div class="section-note">Bu liste sevkiyat çıkışındaki exit_cash alanını salt okunur gösterir. SCNA kaydını değiştirmez.</div><div class="table"><table><thead><tr><th>SCNA</th><th>Plaka</th><th>Şoför</th><th>Verilen</th><th>Çıkış Tarihi</th></tr></thead><tbody>${body}</tbody></table></div>`,null);
}
"""
anchor='function openShipmentCashDetails(){'
if anchor not in s: raise RuntimeError('shipment detail function anchor missing')
s=s.replace(anchor,fn+anchor,1)
p.write_text(s,encoding='utf-8'); print('patched shipment cash out')
