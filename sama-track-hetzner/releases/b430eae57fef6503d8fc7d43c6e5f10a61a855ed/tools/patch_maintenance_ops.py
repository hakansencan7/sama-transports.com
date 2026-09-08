from pathlib import Path
import re

p=Path('app.py')
s=p.read_text(encoding='utf-8')

# V4: personel hatali bakım kaydını düzeltebilir + yeni bakımda 3 karakter plaka autocomplete.
# Mevcut V3 kodunun üstüne küçük ve tekrar çalıştırılabilir patch uygular.

# 1) Backend update endpoint
anchor='@app.post("/api/maintenance-operations/{op_id}/finish")'
if '@app.post("/api/maintenance-operations/{op_id}/update")' not in s:
    pos=s.find(anchor)
    if pos<0: raise RuntimeError('maintenance finish anchor not found')
    update_backend=r'''@app.post("/api/maintenance-operations/{op_id}/update")
def maintenance_operations_update(op_id:int,x:MaintenanceOperationIn):
    plate=(x.plate or '').strip().upper()
    reason=(x.reason or '').strip()
    description=(x.description or '').strip()
    hours=max(0,float(x.estimated_hours or 0))
    if not plate: raise HTTPException(400,'Plaka zorunlu.')
    if not reason: raise HTTPException(400,'Bakım nedeni zorunludur.')
    c=db(); _ensure_maintenance_ops(c)
    row=c.execute("SELECT * FROM maintenance_operations WHERE id=?",(op_id,)).fetchone()
    if not row: c.close(); raise HTTPException(404,'Bakım kaydı bulunamadı.')
    dup=c.execute("SELECT 1 FROM maintenance_operations WHERE UPPER(plate)=UPPER(?) AND is_active=1 AND id<>?",(plate,op_id)).fetchone()
    if dup: c.close(); raise HTTPException(409,'Seçilen araç zaten başka bir aktif bakım kaydında.')
    started=row['started_at'] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try: base=datetime.fromisoformat(str(started).replace('Z','').replace('T',' '))
    except: base=datetime.now()
    est=(base+timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S') if hours>0 else None
    c.execute("""UPDATE maintenance_operations SET plate=?,reason=?,description=?,estimated_hours=?,estimated_finish_at=? WHERE id=?""",
              (plate,reason,description,hours,est,op_id))
    c.commit(); c.close()
    audit('MAINTENANCE_UPDATE',plate,f'Bakım kaydı düzeltildi. Neden: {reason}. Tahmini süre: {hours:g} saat','ARAC')
    return {'ok':True,'id':op_id,'plate':plate,'estimated_finish_at':est}

'''
    s=s[:pos]+update_backend+s[pos:]

# 2) İşlem sütununa DÜZENLE ekle. Aktif ve tamamlanmış kayıtlar düzeltilebilir.
old="<td>${Number(x.is_active)===1?`<button class=\"btn green\" onclick=\"finishMaintenanceOp(${x.id},'${String(x.plate||'').replace(/'/g,\"\\\\'\")}')\">BAKIM BİTTİ</button>`:''}</td>"
new="<td><div class=\"compact-actions\"><button class=\"btn secondary\" onclick=\"editMaintenanceOp(${x.id})\">DÜZENLE</button>${Number(x.is_active)===1?`<button class=\"btn green\" onclick=\"finishMaintenanceOp(${x.id},'${String(x.plate||'').replace(/'/g,\"\\\\'\")}')\">BAKIM BİTTİ</button>`:''}</div></td>"
if old in s: s=s.replace(old,new,1)

# 3) Yeni kayıt modalındaki select'i 3 karakter autocomplete input'a çevir.
old_start="async function openMaintenanceStart(){if(!integratedFleetRows.length)await loadIntegratedFleetStatus();const opts=integratedFleetRows.filter(x=>x.operation_state!=='BAKIM').map(x=>`<option value=\"${x.plate}\">${x.plate} — ${integratedStateLabel(x.operation_state)}</option>`).join('');openM('Aracı Bakıma Al',`<div class=\"grid\"><div class=\"field\"><label>Plaka</label><select id=\"moPlate\">${opts}</select></div>"
new_start="async function openMaintenanceStart(){openM('Aracı Bakıma Al',`<div class=\"grid\"><div class=\"field\"><label>Plaka</label><div class=\"autocomplete-wrap\"><input id=\"moPlate\" autocomplete=\"off\" placeholder=\"En az 3 karakter yazın...\" oninput=\"maintenancePlateSearch(this)\"><div id=\"moPlateList\" class=\"autocomplete-list\"></div></div></div>"
if old_start in s: s=s.replace(old_start,new_start,1)

# 4) JS yardımcıları: autocomplete + edit modal.
js_anchor='async function finishMaintenanceOp(id,plate){'
if 'async function maintenancePlateSearch(input)' not in s:
    pos=s.find(js_anchor)
    if pos<0: raise RuntimeError('finishMaintenanceOp JS anchor not found')
    helpers=r'''async function maintenancePlateSearch(input){
  const list=document.getElementById('moPlateList');if(!list)return;
  const q=(input.value||'').trim().toUpperCase();
  if(q.length<3){list.style.display='none';list.innerHTML='';return;}
  try{
    const rows=await api('/api/autocomplete/plates?q='+encodeURIComponent(q));
    const active=new Set((maintenanceOpsRows||[]).filter(x=>Number(x.is_active)===1).map(x=>String(x.plate||'').toUpperCase()));
    const usable=(rows||[]).filter(x=>!active.has(String(x.plate||'').toUpperCase()));
    list.innerHTML=usable.slice(0,20).map(x=>`<div class="autocomplete-item" onclick="selectMaintenancePlate('${String(x.plate||'').replace(/'/g,"\\'")}')"><div class="autocomplete-main">${x.plate||''}</div><div class="autocomplete-sub">${[x.brand,x.model,x.vehicle_type].filter(Boolean).join(' • ')}</div></div>`).join('')||'<div class="autocomplete-item">Uygun plaka bulunamadı.</div>';
    list.style.display='block';
  }catch(e){list.style.display='none';}
}
function selectMaintenancePlate(plate){const i=document.getElementById('moPlate'),l=document.getElementById('moPlateList');if(i)i.value=plate;if(l)l.style.display='none';}
async function editMaintenanceOp(id){
  const x=(maintenanceOpsRows||[]).find(r=>Number(r.id)===Number(id));if(!x)return alert('Bakım kaydı bulunamadı.');
  openM(`${x.plate} — Bakım Kaydını Düzelt`,`<div class="grid"><div class="field"><label>Plaka</label><div class="autocomplete-wrap"><input id="moEditPlate" value="${x.plate||''}" autocomplete="off" oninput="maintenanceEditPlateSearch(this)"><div id="moEditPlateList" class="autocomplete-list"></div></div></div><div class="field"><label>Tahmini Bakım Süresi (Saat)</label><input id="moEditHours" type="number" min="0" step="0.5" value="${Number(x.estimated_hours||0)}"></div><div class="field wide"><label>Bakım Nedeni</label><input id="moEditReason" value="${String(x.reason||'').replace(/\"/g,'&quot;')}"></div><div class="field wide"><label>Açıklama</label><textarea id="moEditDescription" rows="4">${x.description||''}</textarea></div></div>`,async()=>{try{await api('/api/maintenance-operations/'+id+'/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plate:moEditPlate.value,reason:moEditReason.value,description:moEditDescription.value,estimated_hours:Number(moEditHours.value||0)})});closeM();await loadMaintenanceOps();await loadIntegratedFleetStatus();alert('Bakım kaydı düzeltildi.');}catch(e){alert(e.message);}});
}
async function maintenanceEditPlateSearch(input){
  const list=document.getElementById('moEditPlateList');if(!list)return;const q=(input.value||'').trim().toUpperCase();if(q.length<3){list.style.display='none';return;}
  try{const rows=await api('/api/autocomplete/plates?q='+encodeURIComponent(q));list.innerHTML=(rows||[]).slice(0,20).map(x=>`<div class="autocomplete-item" onclick="document.getElementById('moEditPlate').value='${String(x.plate||'').replace(/'/g,"\\'")}';document.getElementById('moEditPlateList').style.display='none'"><div class="autocomplete-main">${x.plate||''}</div><div class="autocomplete-sub">${[x.brand,x.model,x.vehicle_type].filter(Boolean).join(' • ')}</div></div>`).join('');list.style.display='block';}catch(e){list.style.display='none';}
}
'''
    s=s[:pos]+helpers+s[pos:]

p.write_text(s,encoding='utf-8')
print('maintenance V4 edit + plate autocomplete patched')
