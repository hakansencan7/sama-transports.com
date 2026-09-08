from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_ADVANCE_RECIPIENT_AUTOCOMPLETE_V3'
if MARK in s:
    print('already patched'); raise SystemExit(0)

# Backend generic recipient search. Insert before existing driver-search endpoint.
needle="@app.get('/api/advances/driver-search')\ndef advances_driver_search(q:str=''):"
if needle not in s:
    raise SystemExit('driver-search endpoint anchor not found')
backend=r'''# SAMA_ADVANCE_RECIPIENT_AUTOCOMPLETE_V3
@app.get('/api/advances/recipient-search')
def advances_recipient_search(q:str='', recipient_type:str=''):
    q=(q or '').strip(); typ=(recipient_type or '').strip().upper()
    if len(q)<3: return []
    if typ not in ('SOFOR','USTA','PERSONEL','DIGER'): return []
    c=db(); _ensure_advances(c); like='%'+q+'%'
    rows=[dict(r) for r in c.execute("""
      SELECT recipient_name name, recipient_type,
             COUNT(*) record_count,
             SUM(CASE WHEN status IN ('ACIK','KISMI') THEN 1 ELSE 0 END) open_count,
             ROUND(SUM(CASE WHEN status IN ('ACIK','KISMI') THEN MAX(amount-settled_amount,0) ELSE 0 END),2) open_balance,
             MAX(id) last_id
      FROM cash_advances
      WHERE recipient_type=? AND TRIM(COALESCE(recipient_name,''))<>''
        AND UPPER(recipient_name) LIKE UPPER(?)
      GROUP BY UPPER(TRIM(recipient_name)),recipient_type
      ORDER BY CASE WHEN SUM(CASE WHEN status IN ('ACIK','KISMI') THEN 1 ELSE 0 END)>0 THEN 0 ELSE 1 END,
               MAX(id) DESC
      LIMIT 30
    """,(typ,like))]
    c.close(); return rows

'''
s=s.replace(needle,backend+needle,1)

# Replace recipient type changed + driver search with generic behavior, while preserving driver master lookup for SOFOR.
start=s.find('function advanceRecipientTypeChanged(){')
end=s.find('function selectAdvanceDriver(i)', start)
if start<0 or end<0:
    raise SystemExit('advance autocomplete JS anchors not found')
# include selectAdvanceDriver function body through its closing line
end2=s.find('\n\nfunction ', end)
if end2<0:
    raise SystemExit('selectAdvanceDriver end anchor not found')

js=r'''function advanceRecipientTypeChanged(){
 window._advanceDriverSelected=false;
 window._advanceRecipientSelected=false;
 const hint=document.getElementById('aDriverHint'),lst=document.getElementById('aDriverList'),name=document.getElementById('aName');
 if(lst){lst.innerHTML='';lst.style.display='none';}
 if(name){name.value='';name.focus();}
 const typ=document.getElementById('aType')?.value||'';
 if(hint)hint.textContent=typ==='SOFOR'?'Kayıtlı şoförü seçin. 3 harften sonra arama başlar.':'Kayıtlı '+(typ==='USTA'?'usta':typ==='PERSONEL'?'personel':'kişi')+' için 3 harf yazın.';
}
// SAMA_ADVANCE_AUTOCOMPLETE_V3
function advanceDriverSearch(el){
 window._advanceDriverSelected=false;
 window._advanceRecipientSelected=false;
 const typ=document.getElementById('aType')?.value||'',lst=document.getElementById('aDriverList'),hint=document.getElementById('aDriverHint');
 if(!lst)return;
 const q=(el.value||'').trim(); clearTimeout(window._advanceDriverTimer);
 if(q.length<3){lst.style.display='none';lst.innerHTML='';if(hint)hint.textContent='En az 3 harf yazın.';return;}
 if(hint)hint.textContent='Aranıyor...';
 lst.innerHTML='<div class="autocomplete-item"><div class="autocomplete-sub">Aranıyor...</div></div>';lst.style.display='block';
 window._advanceDriverTimer=setTimeout(async()=>{
   let rows=[];
   // Önce Avans Takip içindeki mevcut cari/kişi kayıtlarını ara.
   try{
     const rec=await api('/api/advances/recipient-search?q='+encodeURIComponent(q)+'&recipient_type='+encodeURIComponent(typ));
     if(Array.isArray(rec)) rows=rec.map(x=>({kind:'RECIPIENT',name:x.name||'',open_count:Number(x.open_count||0),open_balance:Number(x.open_balance||0),record_count:Number(x.record_count||0)}));
   }catch(e){}

   // Şoförde ayrıca ana şoför listesini de tara; mevcut avans kaydı olmasa bile seçilebilsin.
   if(typ==='SOFOR'){
     let drv=[];
     try{drv=await api('/api/advances/driver-search?q='+encodeURIComponent(q));}catch(e){}
     if(!Array.isArray(drv)||!drv.length){
       try{
         const r=await api('/api/fleet/drivers');
         const all=Array.isArray(r)?r:(r?.rows||[]),Q=q.toLocaleUpperCase('tr-TR');
         drv=all.filter(x=>Number(x.is_active)!==0 && [x.name,x.d_no,x.phone,x.last_plate].join(' ').toLocaleUpperCase('tr-TR').includes(Q))
           .slice(0,30).map(x=>({name:x.name||'',d_no:x.d_no||'',phone:x.phone||'',plate:x.last_plate||''}));
       }catch(e){drv=[];}
     }
     const seen=new Set(rows.map(x=>String(x.name||'').trim().toLocaleUpperCase('tr-TR')));
     for(const x of (drv||[])){
       const k=String(x.name||'').trim().toLocaleUpperCase('tr-TR');
       if(k&&!seen.has(k)){seen.add(k);rows.push({kind:'DRIVER',name:x.name||'',d_no:x.d_no||'',phone:x.phone||'',plate:x.plate||''});}
     }
   }

   if(!rows.length){
     lst.innerHTML='<div class="autocomplete-item"><div class="autocomplete-sub">Kayıtlı kişi/cari bulunamadı</div></div>';lst.style.display='block';
     if(hint)hint.textContent=typ==='SOFOR'?'⚠ Kayıtlı şoför bulunamadı. Kaydederken yeni şoför oluşturma onayı istenecek.':'Kayıtlı cari bulunamadı; yeni isim olarak kaydedilebilir.';
     return;
   }
   window._advanceDriverMatches=rows;
   if(hint)hint.textContent=rows.length+' kayıt bulundu.';
   lst.innerHTML=rows.slice(0,30).map((x,i)=>{
     const sub=x.kind==='RECIPIENT'
       ? ((x.open_count>0?'AÇIK CARİ • '+x.open_count+' kayıt • Bakiye '+money(x.open_balance):'Geçmiş cari • '+x.record_count+' kayıt'))
       : ([x.d_no,x.phone,x.plate].filter(Boolean).join(' • ')||'Kayıtlı şoför');
     return `<div class="autocomplete-item" onmousedown="event.preventDefault();selectAdvanceDriver(${i})"><div class="autocomplete-main">${advEsc?advEsc(x.name||''):x.name||''}</div><div class="autocomplete-sub">${sub}</div></div>`;
   }).join('');
   lst.style.display='block';
 },180);
}
function selectAdvanceDriver(i){
 const x=(window._advanceDriverMatches||[])[i];if(!x)return;
 const typ=document.getElementById('aType')?.value||'';
 document.getElementById('aName').value=x.name||'';
 if(typ==='SOFOR'&&x.plate)document.getElementById('aPlate').value=x.plate;
 window._advanceRecipientSelected=true;
 window._advanceDriverSelected=(typ!=='SOFOR'||x.kind==='DRIVER'||x.kind==='RECIPIENT');
 const lst=document.getElementById('aDriverList');if(lst)lst.style.display='none';
 const hint=document.getElementById('aDriverHint');if(hint)hint.textContent=x.open_count>0?'✓ Açık cari seçildi.':'✓ Kayıtlı kişi seçildi.';
}
'''
s=s[:start]+js+s[end2:]

# In new advance form, make placeholder generic rather than driver-only.
s=s.replace('placeholder="Şoförde 3 harften sonra arar"','placeholder="3 harften sonra kayıtlı cari/kişi ara"')

p.write_text(s,encoding='utf-8')
print('patched advance recipient autocomplete v3')
