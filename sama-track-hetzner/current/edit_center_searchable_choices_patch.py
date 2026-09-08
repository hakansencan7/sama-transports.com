# Searchable edit-center choices for Driver / Customer / Area.
# Keeps the visible field writable for filtering while storing authoritative DB ids
# in hidden inputs. Driver choices come from the full driver masters, not only
# drivers currently attached to a vehicle.

from typing import Optional
from pydantic import BaseModel
import entry_other_edit_unlock_patch as base

app = base.app
core = base.core
html = core.HTML

MARK = "SAMA_EDIT_SEARCHABLE_CHOICES_V1"


def _norm(value):
    return " ".join(str(value or "").strip().upper().split())


@app.get("/api/trips-tools/edit-choices")
def sama_edit_choices():
    c = core.db()
    try:
        driver_rows = [dict(r) for r in c.execute(
            "SELECT id,name,phone,d_no,active FROM drivers ORDER BY name,id"
        )]
        fleet_rows = [dict(r) for r in c.execute(
            "SELECT id,name,phone,d_no,is_active FROM fleet_drivers ORDER BY name,id"
        )]
        customers = [dict(r) for r in c.execute(
            "SELECT id,name,active FROM customers ORDER BY name,id"
        )]
        areas = [dict(r) for r in c.execute(
            "SELECT id,name,active FROM areas ORDER BY name,id"
        )]
    finally:
        c.close()

    # Keep every canonical trip-driver row, including passive/history rows.
    drivers = []
    canonical_names = set()
    for row in driver_rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        canonical_names.add(_norm(name))
        drivers.append({
            "id": row.get("id"),
            "fleet_id": None,
            "name": name,
            "phone": str(row.get("phone") or "").strip(),
            "d_no": str(row.get("d_no") or "").strip(),
            "is_active": 1 if int(row.get("active") or 0) else 0,
            "source": "drivers",
        })

    # Fleet-only drivers used to disappear from Edit Center because the old UI
    # built its list from vehicles. Show them too. A canonical drivers.id is
    # created only when the operator actually selects one for a shipment.
    fleet_seen = set()
    for row in fleet_rows:
        name = str(row.get("name") or "").strip()
        key = _norm(name)
        if not name or key in canonical_names:
            continue
        sig = (key, str(row.get("d_no") or "").strip().upper())
        if sig in fleet_seen:
            continue
        fleet_seen.add(sig)
        drivers.append({
            "id": None,
            "fleet_id": row.get("id"),
            "name": name,
            "phone": str(row.get("phone") or "").strip(),
            "d_no": str(row.get("d_no") or "").strip(),
            "is_active": 1 if int(row.get("is_active") or 0) else 0,
            "source": "fleet_drivers",
        })

    drivers.sort(key=lambda x: (_norm(x.get("name")), _norm(x.get("d_no"))))
    return {
        "drivers": drivers,
        "customers": customers,
        "areas": areas,
    }


class EditDriverResolveIn(BaseModel):
    name: str = ""
    fleet_id: Optional[int] = None


@app.post("/api/trips-tools/resolve-driver")
def sama_resolve_edit_driver(x: EditDriverResolveIn):
    name = str(x.name or "").strip()
    if not name:
        raise core.HTTPException(400, "Şoför seçin.")

    c = core.db()
    try:
        row = c.execute(
            "SELECT id,name,phone,d_no,active FROM drivers WHERE UPPER(TRIM(name))=UPPER(TRIM(?)) ORDER BY active DESC,id LIMIT 1",
            (name,),
        ).fetchone()
        if row:
            return {"id": row["id"], "name": row["name"]}

        fleet = None
        if x.fleet_id:
            fleet = c.execute(
                "SELECT id,name,phone,d_no,is_active FROM fleet_drivers WHERE id=?",
                (x.fleet_id,),
            ).fetchone()
        if not fleet:
            fleet = c.execute(
                "SELECT id,name,phone,d_no,is_active FROM fleet_drivers WHERE UPPER(TRIM(name))=UPPER(TRIM(?)) ORDER BY is_active DESC,id LIMIT 1",
                (name,),
            ).fetchone()
        if not fleet:
            raise core.HTTPException(400, "Şoför listede bulunamadı. Listeden seçim yapın.")

        cur = c.execute(
            "INSERT INTO drivers(name,phone,d_no,active) VALUES(?,?,?,?)",
            (
                str(fleet["name"] or "").strip(),
                str(fleet["phone"] or "").strip(),
                str(fleet["d_no"] or "").strip(),
                1 if int(fleet["is_active"] or 0) else 0,
            ),
        )
        c.commit()
        new_id = cur.lastrowid
        try:
            core.audit("EDIT_DRIVER_SYNC", str(fleet["name"] or "").strip(), "Fleet şoförü sevkiyat şoför listesine eşlendi")
        except Exception:
            pass
        return {"id": new_id, "name": str(fleet["name"] or "").strip()}
    finally:
        c.close()


if MARK not in html:
    old_fields = '''<div class="field"><label>Şoför</label><select id="eDriver"><option value="">Seçin</option>${drivers}</select></div>
        <div class="field"><label>Müşteri</label><select id="eCustomer"><option value="">Seçin</option>${customers}</select></div>
        <div class="field"><label>Bölge</label><select id="eArea"><option value="">Seçin</option>${areas}</select></div>'''
    new_fields = '''<div class="field"><label>Şoför</label><div class="autocomplete-wrap"><input id="eDriver" autocomplete="off" placeholder="Şoför yazın veya seçin" onfocus="samaEditComboOpen('driver')" oninput="samaEditComboTyped('driver')"><input id="eDriverId" type="hidden"><div id="eDriverList" class="autocomplete-list"></div></div></div>
        <div class="field"><label>Müşteri</label><div class="autocomplete-wrap"><input id="eCustomer" autocomplete="off" placeholder="Müşteri yazın veya seçin" onfocus="samaEditComboOpen('customer')" oninput="samaEditComboTyped('customer')"><input id="eCustomerId" type="hidden"><div id="eCustomerList" class="autocomplete-list"></div></div></div>
        <div class="field"><label>Bölge</label><div class="autocomplete-wrap"><input id="eArea" autocomplete="off" placeholder="Bölge yazın veya seçin" onfocus="samaEditComboOpen('area')" oninput="samaEditComboTyped('area')"><input id="eAreaId" type="hidden"><div id="eAreaList" class="autocomplete-list"></div></div></div>'''
    if old_fields not in html:
        raise RuntimeError("Edit Center driver/customer/area field anchor not found")
    html = html.replace(old_fields, new_fields, 1)

    old_values = '''eDriver.value=editCx.driver_id||'';
    eCustomer.value=editCx.customer_id||'';
    eArea.value=editCx.area_id||'';'''
    new_values = '''eDriver.value=editCx.driver_name||'';
    eDriverId.value=editCx.driver_id||'';
    eCustomer.value=editCx.customer_name||'';
    eCustomerId.value=editCx.customer_id||'';
    eArea.value=editCx.area_name||'';
    eAreaId.value=editCx.area_id||'';'''
    if old_values not in html:
        raise RuntimeError("Edit Center current-value anchor not found")
    html = html.replace(old_values, new_values, 1)

    old_payload = '''driver_id:eDriver.value?Number(eDriver.value):null,
    area_id:eArea.value?Number(eArea.value):null,
    cargo_category_id:eCargo.value?Number(eCargo.value):null,
    cargo_type:eCargoType.value,
    customer_id:eCustomer.value?Number(eCustomer.value):null,'''
    new_payload = '''driver_id:eDriverId.value?Number(eDriverId.value):null,
    area_id:eAreaId.value?Number(eAreaId.value):null,
    cargo_category_id:eCargo.value?Number(eCargo.value):null,
    cargo_type:eCargoType.value,
    customer_id:eCustomerId.value?Number(eCustomerId.value):null,'''
    if old_payload not in html:
        raise RuntimeError("Edit Center payload anchor not found")
    html = html.replace(old_payload, new_payload, 1)

    combo_js = r'''
// SAMA_EDIT_SEARCHABLE_CHOICES_V1
let SAMA_EDIT_CHOICES=null;
const SAMA_EDIT_COMBO={
  driver:{input:'eDriver',hidden:'eDriverId',list:'eDriverList',rows:'drivers',label:'Şoför'},
  customer:{input:'eCustomer',hidden:'eCustomerId',list:'eCustomerList',rows:'customers',label:'Müşteri'},
  area:{input:'eArea',hidden:'eAreaId',list:'eAreaList',rows:'areas',label:'Bölge'}
};
function samaEditNorm(v){return String(v||'').trim().toLocaleUpperCase('tr-TR').replace(/\s+/g,' ');}
async function samaEditChoicesLoad(){
  if(SAMA_EDIT_CHOICES)return SAMA_EDIT_CHOICES;
  SAMA_EDIT_CHOICES=await api('/api/trips-tools/edit-choices');
  return SAMA_EDIT_CHOICES;
}
function samaEditComboRows(type){
  const cfg=SAMA_EDIT_COMBO[type];
  return (SAMA_EDIT_CHOICES&&cfg&&SAMA_EDIT_CHOICES[cfg.rows])||[];
}
async function samaEditComboOpen(type){
  try{await samaEditChoicesLoad();samaEditComboRender(type);}catch(e){console.error(e);}
}
function samaEditComboTyped(type){
  const cfg=SAMA_EDIT_COMBO[type];if(!cfg)return;
  const hidden=document.getElementById(cfg.hidden);if(hidden)hidden.value='';
  samaEditComboRender(type);
}
function samaEditComboRender(type){
  const cfg=SAMA_EDIT_COMBO[type];if(!cfg)return;
  const input=document.getElementById(cfg.input),list=document.getElementById(cfg.list);
  if(!input||!list||!SAMA_EDIT_CHOICES)return;
  const q=samaEditNorm(input.value);
  const rows=samaEditComboRows(type).filter(x=>{
    const hay=samaEditNorm([x.name,x.d_no,x.phone].filter(Boolean).join(' '));
    return !q||hay.includes(q);
  }).slice(0,500);
  list.innerHTML='';
  if(!rows.length){list.style.display='none';return;}
  rows.forEach(row=>{
    const item=document.createElement('div');item.className='autocomplete-item';
    const main=document.createElement('div');main.className='autocomplete-main';main.textContent=String(row.name||'');
    const sub=document.createElement('div');sub.className='autocomplete-sub';
    const bits=[];
    if(row.d_no)bits.push(row.d_no);if(row.phone)bits.push(row.phone);if(Number(row.active??row.is_active)===0)bits.push('PASİF');
    sub.textContent=bits.join(' • ');
    item.appendChild(main);if(bits.length)item.appendChild(sub);
    item.addEventListener('mousedown',async ev=>{ev.preventDefault();await samaEditComboChoose(type,row);});
    list.appendChild(item);
  });
  list.style.display='block';
}
async function samaEditComboChoose(type,row){
  const cfg=SAMA_EDIT_COMBO[type];if(!cfg)return;
  const input=document.getElementById(cfg.input),hidden=document.getElementById(cfg.hidden),list=document.getElementById(cfg.list);
  let id=row&&row.id;
  if(type==='driver'&&!id){
    const r=await api('/api/trips-tools/resolve-driver',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:row.name||'',fleet_id:row.fleet_id||null})});
    id=r.id;row.id=id;
  }
  if(input)input.value=String(row.name||'');
  if(hidden)hidden.value=id?String(id):'';
  if(list)list.style.display='none';
}
async function samaEditComboEnsureOne(type){
  const cfg=SAMA_EDIT_COMBO[type];if(!cfg)return;
  const input=document.getElementById(cfg.input),hidden=document.getElementById(cfg.hidden);
  if(!input||!hidden)return;
  const value=String(input.value||'').trim();
  if(!value){hidden.value='';return;}
  if(hidden.value)return;
  await samaEditChoicesLoad();
  const exact=samaEditComboRows(type).filter(x=>samaEditNorm(x.name)===samaEditNorm(value));
  if(exact.length!==1)throw new Error(cfg.label+' için listeden bir kayıt seçin.');
  await samaEditComboChoose(type,exact[0]);
}
async function samaEditComboEnsureIds(){
  await samaEditComboEnsureOne('driver');
  await samaEditComboEnsureOne('customer');
  await samaEditComboEnsureOne('area');
}
document.addEventListener('mousedown',ev=>{
  Object.values(SAMA_EDIT_COMBO).forEach(cfg=>{
    const input=document.getElementById(cfg.input),list=document.getElementById(cfg.list);
    if(list&&input&&ev.target!==input&&!list.contains(ev.target))list.style.display='none';
  });
});
'''
    anchor = "function editPayload(){"
    if anchor not in html:
        raise RuntimeError("Edit Center payload function anchor not found")
    html = html.replace(anchor, combo_js + "\n" + anchor, 1)

    validate_anchor = "async function validateAndSaveEdit(){\n  const scna=(editScna.value||'').trim().toUpperCase();"
    validate_repl = "async function validateAndSaveEdit(){\n  try{await samaEditComboEnsureIds();}catch(e){alert(e.message);return;}\n  const scna=(editScna.value||'').trim().toUpperCase();"
    if validate_anchor not in html:
        raise RuntimeError("Edit Center validate anchor not found")
    html = html.replace(validate_anchor, validate_repl, 1)

    core.HTML = html
