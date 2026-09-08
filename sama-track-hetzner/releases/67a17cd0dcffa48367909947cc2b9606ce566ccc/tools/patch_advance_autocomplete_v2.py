from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_ADVANCE_AUTOCOMPLETE_V2'
if MARK in s:
    print('already patched'); raise SystemExit(0)

# Make driver the practical default for new advance records.
old='''<select id="aType" onchange="advanceRecipientTypeChanged()"><option value="USTA">Usta</option><option value="SOFOR">Şoför</option><option value="PERSONEL">Personel</option><option value="DIGER">Diğer</option></select>'''
new='''<select id="aType" onchange="advanceRecipientTypeChanged()"><option value="SOFOR">Şoför</option><option value="USTA">Usta</option><option value="PERSONEL">Personel</option><option value="DIGER">Diğer</option></select>'''
if old not in s: raise RuntimeError('advance type select anchor not found')
s=s.replace(old,new,1)

oldfunc='''function advanceDriverSearch(el){
 window._advanceDriverSelected=false;
 const typ=document.getElementById('aType')?.value,lst=document.getElementById('aDriverList'),hint=document.getElementById('aDriverHint');
 if(!lst)return;
 if(typ!=='SOFOR'){lst.style.display='none';if(hint)hint.textContent='';return;}
 const q=(el.value||'').trim(); clearTimeout(window._advanceDriverTimer);
 if(q.length<3){lst.style.display='none';lst.innerHTML='';if(hint)hint.textContent='En az 3 harf yazın.';return;}
 window._advanceDriverTimer=setTimeout(async()=>{try{const rows=await api('/api/advances/driver-search?q='+encodeURIComponent(q));if(!rows.length){lst.style.display='none';lst.innerHTML='';if(hint)hint.textContent='⚠ Kayıtlı şoför bulunamadı. Kaydederken yeni şoför oluşturma onayı istenecek.';return;}if(hint)hint.textContent=rows.length+' kayıt bulundu.';lst.innerHTML=rows.map((x,i)=>`<div class="autocomplete-item" onclick="selectAdvanceDriver(${i})"><div class="autocomplete-main">${x.name||''}</div><div class="autocomplete-sub">${x.d_no||''}${x.phone?' • '+x.phone:''}${x.plate?' • '+x.plate:''}</div></div>`).join('');window._advanceDriverMatches=rows;lst.style.display='block';}catch(e){lst.style.display='none';if(hint)hint.textContent='Şoför araması yapılamadı: '+e.message;}},220);
}'''
newfunc='''# SAMA_ADVANCE_AUTOCOMPLETE_V2
function advanceDriverSearch(el){
 window._advanceDriverSelected=false;
 const typ=document.getElementById('aType')?.value,lst=document.getElementById('aDriverList'),hint=document.getElementById('aDriverHint');
 if(!lst)return;
 if(typ!=='SOFOR'){lst.style.display='none';if(hint)hint.textContent='';return;}
 const q=(el.value||'').trim(); clearTimeout(window._advanceDriverTimer);
 if(q.length<3){lst.style.display='none';lst.innerHTML='';if(hint)hint.textContent='En az 3 harf yazın.';return;}
 if(hint)hint.textContent='Aranıyor...';
 lst.innerHTML='<div class="autocomplete-item"><div class="autocomplete-sub">Aranıyor...</div></div>';lst.style.display='block';
 window._advanceDriverTimer=setTimeout(async()=>{
   let rows=[];
   try{rows=await api('/api/advances/driver-search?q='+encodeURIComponent(q));}catch(e){}
   if(!Array.isArray(rows)||!rows.length){
     try{
       const r=await api('/api/fleet/drivers');
       const all=Array.isArray(r)?r:(r?.rows||[]),Q=q.toLocaleUpperCase('tr-TR');
       rows=all.filter(x=>Number(x.is_active)!==0 && [x.name,x.d_no,x.phone,x.last_plate].join(' ').toLocaleUpperCase('tr-TR').includes(Q))
         .slice(0,30).map(x=>({name:x.name||'',d_no:x.d_no||'',phone:x.phone||'',plate:x.last_plate||''}));
     }catch(e){rows=[];}
   }
   if(!rows.length){lst.innerHTML='<div class="autocomplete-item"><div class="autocomplete-sub">Kayıtlı şoför bulunamadı</div></div>';lst.style.display='block';if(hint)hint.textContent='⚠ Kayıtlı şoför bulunamadı. Kaydederken yeni şoför oluşturma onayı istenecek.';return;}
   window._advanceDriverMatches=rows;
   if(hint)hint.textContent=rows.length+' kayıt bulundu.';
   lst.innerHTML=rows.map((x,i)=>`<div class="autocomplete-item" onmousedown="event.preventDefault();selectAdvanceDriver(${i})"><div class="autocomplete-main">${x.name||''}</div><div class="autocomplete-sub">${x.d_no||''}${x.phone?' • '+x.phone:''}${x.plate?' • '+x.plate:''}</div></div>`).join('');
   lst.style.display='block';
 },180);
}'''
if oldfunc not in s: raise RuntimeError('advance search function anchor not found')
s=s.replace(oldfunc,newfunc,1)

# When selected, force recipient type to driver and keep dropdown stable.
old="function selectAdvanceDriver(i){const x=(window._advanceDriverMatches||[])[i];if(!x)return;document.getElementById('aName').value=x.name||'';if(x.plate)document.getElementById('aPlate').value=x.plate;window._advanceDriverSelected=true;const lst=document.getElementById('aDriverList');if(lst)lst.style.display='none';const hint=document.getElementById('aDriverHint');if(hint)hint.textContent='✓ Kayıtlı şoför seçildi.';}"
new="function selectAdvanceDriver(i){const x=(window._advanceDriverMatches||[])[i];if(!x)return;const typ=document.getElementById('aType');if(typ)typ.value='SOFOR';document.getElementById('aName').value=x.name||'';if(x.plate)document.getElementById('aPlate').value=x.plate;window._advanceDriverSelected=true;const lst=document.getElementById('aDriverList');if(lst)lst.style.display='none';const hint=document.getElementById('aDriverHint');if(hint)hint.textContent='✓ Kayıtlı şoför seçildi.';}"
if old not in s: raise RuntimeError('select advance driver anchor not found')
s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')
print('patched advance autocomplete v2')
