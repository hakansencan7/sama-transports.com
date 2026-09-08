import print_audit_patch as print_patch
from fastapi import HTTPException, Request

app = print_patch.app
core = print_patch.core


def _admin_user(request: Request):
    user = getattr(request.state, 'auth_user', None) or {}
    if str(user.get('role') or '').upper() != 'ADMIN':
        raise HTTPException(403, 'Sadece ADMIN plaka silebilir.')
    return user


@app.delete('/api/fleet/vehicles/{plate}/hard-delete')
def fleet_vehicle_hard_delete(plate: str, request: Request):
    _admin_user(request)
    p = str(plate or '').strip().upper()
    if not p:
        raise HTTPException(400, 'Plaka zorunlu.')

    c = core.db()
    try:
        exists = c.execute('SELECT 1 FROM fleet_vehicles WHERE UPPER(TRIM(plate))=?', (p,)).fetchone()
        if not exists:
            raise HTTPException(404, f'Plaka bulunamadı: {p}')

        c.execute('DELETE FROM vehicle_operations WHERE UPPER(TRIM(plate))=?', (p,))
        c.execute('DELETE FROM fleet_vehicles WHERE UPPER(TRIM(plate))=?', (p,))
        c.execute('DELETE FROM vehicles WHERE UPPER(TRIM(plate))=?', (p,))
        c.commit()
    finally:
        c.close()

    try:
        core.audit('FLEET_VEHICLE_DELETE', p, 'Filo yönetiminden hatalı plaka silindi', 'FILO')
    except Exception:
        pass
    return {'ok': True, 'plate': p}


html = core.HTML

old_row = '''<button class=\"btn secondary\" onclick=\"openFleetVehicle('${x.plate}')\">Düzenle</button> <button class=\"btn ${x.is_active?'orange':'green'}\" onclick=\"toggleFleetVehicle('${x.plate}',${x.is_active?0:1})\">${x.is_active?'Pasife Al':'Aktif Et'}</button>'''
new_row = old_row + ''' <button class=\"btn\" style=\"background:#dc2626;color:#fff\" onclick=\"deleteFleetVehicle('${x.plate}')\">Sil</button>'''

if old_row in html:
    html = html.replace(old_row, new_row, 1)

anchor = "function openFleetVehicle(plate=''){"
helper = r'''async function deleteFleetVehicle(plate){
  const p=String(plate||'').trim().toUpperCase();
  if(!p)return;
  if(!confirm(p+' plakası Filo Yönetimi ana listesinden tamamen silinsin mi?\n\nSevkiyat geçmişi silinmez.'))return;
  try{
    await api('/api/fleet/vehicles/'+encodeURIComponent(p)+'/hard-delete',{method:'DELETE'});
    await loadFleetManagement();
    alert(p+' silindi.');
  }catch(e){alert(e.message);}
}

'''
if anchor in html and 'async function deleteFleetVehicle(plate)' not in html:
    html = html.replace(anchor, helper + anchor, 1)

core.HTML = html
print('[SAMA] Safe fleet plate delete active: inline existing JS only')
