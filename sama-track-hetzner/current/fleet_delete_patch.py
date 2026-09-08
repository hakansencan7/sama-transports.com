import print_audit_patch as print_patch
from fastapi import HTTPException, Request

app = print_patch.app
core = print_patch.core


def _is_admin(request: Request) -> bool:
    user = getattr(request.state, 'auth_user', None) or {}
    return str(user.get('role') or '').upper() == 'ADMIN'


@app.delete('/api/fleet/vehicle-delete/{plate}')
def fleet_vehicle_delete(plate: str, request: Request):
    if not _is_admin(request):
        raise HTTPException(403, 'Sadece ADMIN plaka silebilir.')
    p = str(plate or '').strip().upper()
    if not p:
        raise HTTPException(400, 'Plaka zorunlu.')

    c = core.db()
    try:
        exists_fleet = c.execute('SELECT 1 FROM fleet_vehicles WHERE UPPER(TRIM(plate))=?', (p,)).fetchone()
        exists_legacy = c.execute('SELECT 1 FROM vehicles WHERE UPPER(TRIM(plate))=?', (p,)).fetchone()
        if not exists_fleet and not exists_legacy:
            raise HTTPException(404, f'Plaka bulunamadı: {p}')

        # Master kayıtları ve güncel operasyon durumunu kaldır. Sevkiyat geçmişine dokunma.
        c.execute('DELETE FROM vehicle_operations WHERE UPPER(TRIM(plate))=?', (p,))
        c.execute('DELETE FROM fleet_vehicles WHERE UPPER(TRIM(plate))=?', (p,))
        c.execute('DELETE FROM vehicles WHERE UPPER(TRIM(plate))=?', (p,))
        c.commit()
    finally:
        c.close()

    try:
        core.audit('FLEET_VEHICLE_DELETE', p, 'Filo yönetiminden plaka silindi', 'FILO')
    except Exception:
        pass
    return {'ok': True, 'plate': p}


html = core.HTML
ui = r'''
<script>
async function samaFleetDeletePlate(){
  const raw=prompt('Silinecek plakayı yazın. Birden fazla plaka için virgül kullanabilirsiniz.');
  if(!raw)return;
  const plates=[...new Set(raw.split(/[,;\n]+/).map(x=>x.trim().toUpperCase()).filter(Boolean))];
  if(!plates.length)return;
  if(!confirm(plates.join(', ')+'\n\nBu plakalar Filo Yönetimi ana listesinden silinecek. Sevkiyat geçmişi silinmeyecek. Devam edilsin mi?'))return;
  let ok=[],err=[];
  for(const p of plates){
    try{
      await api('/api/fleet/vehicle-delete/'+encodeURIComponent(p),{method:'DELETE'});
      ok.push(p);
    }catch(e){err.push(p+': '+e.message);}
  }
  alert((ok.length?'Silindi: '+ok.join(', '):'Hiçbir plaka silinmedi.')+(err.length?'\n\nHata:\n'+err.join('\n'):''));
  if(ok.length) location.reload();
}
function samaAttachFleetDeleteButton(){
  if(document.getElementById('samaFleetDeleteBtn'))return;
  const candidates=[...document.querySelectorAll('button')];
  let anchor=candidates.find(b=>/araç ekle|yeni araç|\+\s*araç/i.test((b.innerText||'').trim()));
  if(!anchor){
    const nodes=[...document.querySelectorAll('h1,h2,h3,b,strong,div')].filter(x=>/filo yönet/i.test((x.innerText||'').trim()));
    if(nodes.length) anchor=nodes[0];
  }
  if(!anchor)return;
  const btn=document.createElement('button');
  btn.id='samaFleetDeleteBtn';btn.type='button';btn.className='btn';btn.innerText='PLAKA SİL';
  btn.style.cssText='background:#dc2626;color:#fff;border:none;margin-left:8px';
  btn.onclick=samaFleetDeletePlate;
  if(anchor.tagName==='BUTTON') anchor.insertAdjacentElement('afterend',btn); else anchor.appendChild(btn);
}
document.addEventListener('DOMContentLoaded',()=>{samaAttachFleetDeleteButton();new MutationObserver(samaAttachFleetDeleteButton).observe(document.body,{childList:true,subtree:true});});
</script>
'''
if '</body>' in html:
    html = html.replace('</body>', ui + '\n</body>', 1)
else:
    html += ui
core.HTML = html
print('[SAMA] Fleet plate delete active: ADMIN only')
