from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='# SAMA_ADVANCE_DRIVER_AUTOCOMPLETE_V1'
if MARK in s:
    print('already patched'); raise SystemExit(0)

# Backend: search existing drivers and optionally create missing driver.
anchor="@app.get('/api/advances')\ndef advances_list(status:str=''):"
if anchor not in s: raise RuntimeError('advance backend anchor not found')
backend=r'''# SAMA_ADVANCE_DRIVER_AUTOCOMPLETE_V1
@app.get('/api/advances/driver-search')
def advances_driver_search(q:str=''):
    q=(q or '').strip()
    if len(q)<3: return []
    c=db()
    like='%'+q+'%'
    rows=[]
    # fleet_drivers is the master list; plate is resolved from current fleet assignment when possible.
    try:
        rows=[dict(r) for r in c.execute("""SELECT d.name,d.phone,d.d_no,
          COALESCE((SELECT fv.plate FROM fleet_vehicles fv WHERE UPPER(TRIM(COALESCE(fv.driver_name,'')))=UPPER(TRIM(d.name)) AND COALESCE(fv.is_active,1)=1 LIMIT 1),'') plate
          FROM fleet_drivers d WHERE COALESCE(d.is_active,1)=1 AND (d.name LIKE ? OR d.phone LIKE ? OR d.d_no LIKE ?)
          ORDER BY d.name LIMIT 20""",(like,like,like))]
    except Exception:
        try:
            rows=[dict(r) for r in c.execute("SELECT name,phone,d_no,'' plate FROM drivers WHERE name LIKE ? OR phone LIKE ? OR d_no LIKE ? ORDER BY name LIMIT 20",(like,like,like))]
        except Exception:
            rows=[]
    c.close(); return rows

class AdvanceDriverCreateIn(BaseModel):
    name: str = ''
    plate: str = ''

@app.post('/api/advances/driver-create')
def advances_driver_create(x:AdvanceDriverCreateIn):
    name=(x.name or '').strip()
    if len(name)<3: raise HTTPException(400,'Şoför adı en az 3 karakter olmalı.')
    c=db()
    # Never create a duplicate exact name.
    try:
        ex=c.execute("SELECT name FROM fleet_drivers WHERE UPPER(TRIM(name))=UPPER(TRIM(?)) LIMIT 1",(name,)).fetchone()
        if ex: c.close(); return {'ok':True,'created':False,'name':ex['name']}
        cols=[r['name'] for r in c.execute('PRAGMA table_info(fleet_drivers)')]
        data={'name':name}
        if 'is_active' in cols:data['is_active']=1
        if 'created_at' in cols:data['created_at']=None
        keys=list(data.keys()); vals=[data[k] for k in keys]
        ph=','.join('?' for _ in keys)
        c.execute(f"INSERT INTO fleet_drivers({','.join(keys)}) VALUES({ph})",vals)
        c.commit()
    except Exception as e:
        c.rollback(); c.close(); raise HTTPException(400,f'Yeni şoför kaydı oluşturulamadı: {e}')
    c.close()
    return {'ok':True,'created':True,'name':name}

'''
s=s.replace(anchor,backend+anchor,1)

old="""function openAdvanceNew(){openM('Yeni Avans',`<div class=\"grid\"><div class=\"field\"><label>Alıcı Tipi</label><select id=\"aType\"><option value=\"USTA\">Usta</option><option value=\"SOFOR\">Şoför</option><option value=\"PERSONEL\">Personel</option><option value=\"DIGER\">Diğer</option></select></div><div class=\"field\"><label>Ad Soyad / Kişi</label><input id=\"aName\"></div>"""
new="""function openAdvanceNew(){openM('Yeni Avans',`<div class=\"grid\"><div class=\"field\"><label>Alıcı Tipi</label><select id=\"aType\" onchange=\"advanceRecipientTypeChanged()\"><option value=\"USTA\">Usta</option><option value=\"SOFOR\">Şoför</option><option value=\"PERSONEL\">Personel</option><option value=\"DIGER\">Diğer</option></select></div><div class=\"field\"><label>Ad Soyad / Kişi</label><div class=\"autocomplete-wrap\"><input id=\"aName\" autocomplete=\"off\" oninput=\"advanceDriverSearch(this)\" placeholder=\"Şoförde 3 harften sonra arar\"><div id=\"aDriverList\" class=\"autocomplete-list\"></div></div><div id=\"aDriverHint\" class=\"small\"></div></div>"""
if old not in s: raise RuntimeError('new advance modal anchor not found')
s=s.replace(old,new,1)

# Before POST, confirm and create missing driver only for SOFOR.
oldsave="""async()=>{try{await api('/api/advances',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({recipient_type:aType.value,recipient_name:aName.value,plate:aPlate.value,scna:aScna.value,purpose:aPurpose.value,amount:Number(aAmount.value||0),currency:aCurrency.value,note:aNote.value})});"""
newsave="""async()=>{try{if(aType.value==='SOFOR'&&!window._advanceDriverSelected){const nm=aName.value.trim();if(!nm)throw new Error('Şoför adı zorunlu.');const ok=confirm('⚠ Şoför kayıtlarında bu isim seçilmedi veya bulunamadı.\\n\\nYeni şoför kaydı oluşturulacak: '+nm+'\\n\\nDevam etmek istiyor musunuz?');if(!ok)return;const cr=await api('/api/advances/driver-create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:nm,plate:aPlate.value})});aName.value=cr.name||nm;window._advanceDriverSelected=true;}await api('/api/advances',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({recipient_type:aType.value,recipient_name:aName.value,plate:aPlate.value,scna:aScna.value,purpose:aPurpose.value,amount:Number(aAmount.value||0),currency:aCurrency.value,note:aNote.value})});"""
if oldsave not in s: raise RuntimeError('advance save anchor not found')
s=s.replace(oldsave,newsave,1)

js=r'''
window._advanceDriverSelected=false;
window._advanceDriverTimer=null;
function advanceRecipientTypeChanged(){
 window._advanceDriverSelected=false;
 const hint=document.getElementById('aDriverHint'),lst=document.getElementById('aDriverList');
 if(lst){lst.innerHTML='';lst.style.display='none';}
 if(hint)hint.textContent=(document.getElementById('aType')?.value==='SOFOR')?'Kayıtlı şoförü seçin. 3 harften sonra arama başlar.':'';
}
function advanceDriverSearch(el){
 window._advanceDriverSelected=false;
 const typ=document.getElementById('aType')?.value,lst=document.getElementById('aDriverList'),hint=document.getElementById('aDriverHint');
 if(!lst)return;
 if(typ!=='SOFOR'){lst.style.display='none';if(hint)hint.textContent='';return;}
 const q=(el.value||'').trim(); clearTimeout(window._advanceDriverTimer);
 if(q.length<3){lst.style.display='none';lst.innerHTML='';if(hint)hint.textContent='En az 3 harf yazın.';return;}
 window._advanceDriverTimer=setTimeout(async()=>{try{const rows=await api('/api/advances/driver-search?q='+encodeURIComponent(q));if(!rows.length){lst.style.display='none';lst.innerHTML='';if(hint)hint.textContent='⚠ Kayıtlı şoför bulunamadı. Kaydederken yeni şoför oluşturma onayı istenecek.';return;}if(hint)hint.textContent=rows.length+' kayıt bulundu.';lst.innerHTML=rows.map((x,i)=>`<div class="autocomplete-item" onclick="selectAdvanceDriver(${i})"><div class="autocomplete-main">${x.name||''}</div><div class="autocomplete-sub">${x.d_no||''}${x.phone?' • '+x.phone:''}${x.plate?' • '+x.plate:''}</div></div>`).join('');window._advanceDriverMatches=rows;lst.style.display='block';}catch(e){lst.style.display='none';if(hint)hint.textContent='Şoför araması yapılamadı: '+e.message;}},220);
}
function selectAdvanceDriver(i){const x=(window._advanceDriverMatches||[])[i];if(!x)return;document.getElementById('aName').value=x.name||'';if(x.plate)document.getElementById('aPlate').value=x.plate;window._advanceDriverSelected=true;const lst=document.getElementById('aDriverList');if(lst)lst.style.display='none';const hint=document.getElementById('aDriverHint');if(hint)hint.textContent='✓ Kayıtlı şoför seçildi.';}
'''
anchor='let advanceRows=[];'
if anchor not in s: raise RuntimeError('advance JS anchor not found')
s=s.replace(anchor,anchor+'\n'+js,1)
p.write_text(s,encoding='utf-8')
print('patched advance driver autocomplete')
