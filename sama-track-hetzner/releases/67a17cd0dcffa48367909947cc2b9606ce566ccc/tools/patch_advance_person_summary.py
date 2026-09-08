from pathlib import Path

p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='// SAMA_ADVANCE_PERSON_SUMMARY_V1'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

old=""" const rows=advanceRows.filter(x=>(!typ||x.recipient_type===typ)&&(!st||x.status===st)&&(!q||[x.recipient_name,x.plate,x.scna,x.purpose,x.note].join(' ').toLocaleUpperCase('tr-TR').includes(q)));
 advRows.innerHTML=rows.map(x=>`<tr>"""
new=""" const rows=advanceRows.filter(x=>(!typ||x.recipient_type===typ)&&(!st||x.status===st)&&(!q||[x.recipient_name,x.plate,x.scna,x.purpose,x.note].join(' ').toLocaleUpperCase('tr-TR').includes(q)));
 // SAMA_ADVANCE_PERSON_SUMMARY_V1
 const sums={};
 rows.forEach(x=>{
   const cur=(x.currency||'').toUpperCase();
   if(!sums[cur]) sums[cur]={total:0,settled:0,remaining:0};
   sums[cur].total+=Number(x.amount||0);
   sums[cur].settled+=Number(x.settled_amount||0);
   sums[cur].remaining+=Number(x.remaining||0);
 });
 const fmtS=(k)=>Object.entries(sums).map(([cur,v])=>`${money(v[k])} ${cur}`).join(' + ')||'0';
 const names=[...new Set(rows.map(x=>(x.recipient_name||'').trim()).filter(Boolean))];
 const personTitle=(q&&names.length===1)?names[0]:(q?`${rows.length} FİLTRELİ İŞLEM`:'TÜM AVANS HESAPLARI');
 const summary=document.getElementById('advPersonSummary');
 if(summary){
   summary.style.display=(q||typ||st)?'block':'none';
   summary.innerHTML=`<div style=\"font-weight:800;font-size:17px;margin-bottom:8px\">${personTitle}</div><div class=\"cards\"><div class=\"card\">İşlem Sayısı<b>${rows.length}</b></div><div class=\"card\">Toplam Alınan<b>${fmtS('total')}</b></div><div class=\"card\">Fatura / Fiş / İade<b>${fmtS('settled')}</b></div><div class=\"card\">Güncel Bakiye / Borç<b>${fmtS('remaining')}</b></div></div>`;
 }
 advRows.innerHTML=rows.map(x=>`<tr>"""
if old not in s:
    raise RuntimeError('renderAdvances anchor not found')
s=s.replace(old,new,1)

old2='''<div class="cards"><div class="card">Açık Kayıt<b id="advOpen">0</b></div><div class="card">Toplam Verilen<b id="advTotal">0</b></div><div class="card">Belgelenen / İade<b id="advSettled">0</b></div><div class="card">Kalan Açık Bakiye<b id="advRemaining">0</b></div></div>'''
new2=old2+'''\n<div id="advPersonSummary" style="display:none;margin:12px 0;padding:12px;border:1px solid var(--border);border-radius:12px"></div>'''
if old2 not in s:
    raise RuntimeError('advance cards anchor not found')
s=s.replace(old2,new2,1)

# Existing top cards should reflect the currently filtered rows as well, while preserving per-currency correctness in the new summary.
old3=""" const open=advanceRows.filter(x=>x.status!=='KAPANDI'); advOpen.innerText=open.length; advTotal.innerText=money(advanceRows.reduce((a,x)=>a+Number(x.amount||0),0)); advSettled.innerText=money(advanceRows.reduce((a,x)=>a+Number(x.settled_amount||0),0)); advRemaining.innerText=money(open.reduce((a,x)=>a+Number(x.remaining||0),0));"""
new3=""" const open=rows.filter(x=>x.status!=='KAPANDI'); advOpen.innerText=open.length; advTotal.innerText=money(rows.reduce((a,x)=>a+Number(x.amount||0),0)); advSettled.innerText=money(rows.reduce((a,x)=>a+Number(x.settled_amount||0),0)); advRemaining.innerText=money(open.reduce((a,x)=>a+Number(x.remaining||0),0));"""
if old3 not in s:
    raise RuntimeError('advance totals anchor not found')
s=s.replace(old3,new3,1)

p.write_text(s,encoding='utf-8')
print('patched advance person summary')
