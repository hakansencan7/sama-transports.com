import ast
import base64
import re
from io import BytesIO
from pathlib import Path

import app as core
from fastapi.responses import Response

BASE = Path(__file__).resolve().parent


def _load_print_js() -> str:
    source = (BASE / "printer_patch.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PRINT_TRIP_JS":
                    js = ast.literal_eval(node.value)
                    js = js.replace("SAMA TRANSPORTS", "NUKHBAT AL-NAHRAIN")
                    js = js.replace("سما ترانسبورت", "نخبة النهرين")
                    js = js.replace(
                        "const freight=n(x.freight_total||x.excel_freight_au),freightRate=n(x.freight_rate),weight=n(x.net_kg),tank=n(x.tank_start_liters);",
                        "const freight=n(x.excel_freight_au)||(n(x.net_kg)*n(x.freight_rate))||n(x.freight_total),freightRate=n(x.freight_rate),weight=n(x.net_kg),tank=n(x.tank_start_liters);",
                    )
                    js = js.replace(
                        "const d=await api('/api/scna-detail/'+encodeURIComponent(scna));",
                        "const d=await api('/api/scna-detail/'+encodeURIComponent(scna)); const pe=await api('/api/print-entry-expenses/'+encodeURIComponent(scna));",
                    )
                    js = js.replace(
                        "  ];\n  const doc=`",
                        "  ];\n  if(pe&&Array.isArray(pe.rows)){pe.rows.forEach(r=>rows.push(r));}\n  const doc=`",
                    )
                    js = js.replace(
                        ".detail .ar{float:right;direction:rtl;font-size:9.2px}",
                        ".detail .ar{float:right;direction:rtl;font-size:9.2px}.entryExpense td{color:#b00020!important;font-weight:900}.entryReason{display:block;clear:both;font-size:7.8px;font-weight:700;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
                    )
                    js = js.replace(
                        "${rows.map(r=>`<tr><td class=\"no\">${r[0]}</td><td class=\"detail\"><span class=\"en\">${r[1]}</span><span class=\"ar\">${r[2]}</span></td><td class=\"price\">${r[3]}</td><td class=\"amt\">${fmt(r[4])}</td></tr>`).join('')}",
                        "${rows.map(r=>`<tr class=\"${r[5]||''}\"><td class=\"no\">${r[0]}</td><td class=\"detail\"><span class=\"en\">${r[1]}</span><span class=\"ar\">${r[2]}</span>${r[6]?`<span class=\"entryReason\">${esc(r[6])}</span>`:''}</td><td class=\"price\">${r[3]}</td><td class=\"amt\">${fmt(r[4])}</td></tr>`).join('')}",
                    )

                    # Compact A4 frame. Font reductions below are intentionally limited
                    # to the header / trip labels that overflow at this narrow width.
                    js = js.replace("@page{size:A4 portrait;margin:3mm}", "@page{size:A4 portrait;margin:10mm 15mm}")
                    js = js.replace(".toolbar{width:204mm", ".toolbar{width:150mm")
                    js = js.replace(
                        ".sheet{width:204mm;height:289mm;margin:0 auto 8px;background:#fff;padding:1.5mm 2mm;",
                        ".sheet{width:150mm;height:255mm;margin:10mm auto 8px;background:#fff;padding:2mm;",
                    )
                    js = js.replace(
                        ".head{border:1.4px solid #111;display:grid;grid-template-columns:36mm 1fr 48mm;height:48mm}",
                        ".head{border:1.4px solid #111;display:grid;grid-template-columns:30mm minmax(0,1fr) 42mm;height:39mm}",
                    )
                    js = js.replace(
                        ".logoBox{border-right:1px solid #111;padding:1.5mm;display:flex;align-items:center;justify-content:center}.logoBox img{width:32mm;height:42mm;object-fit:contain;filter:grayscale(1) contrast(1.8)}",
                        ".logoBox{border-right:1px solid #111;padding:1mm;display:flex;align-items:center;justify-content:center;overflow:hidden}.logoBox img{width:27mm;height:34mm;object-fit:contain;filter:grayscale(1) contrast(1.8)}",
                    )
                    js = js.replace(
                        ".brandBox{display:grid;grid-template-rows:1fr 11mm}.brandMain{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}.brandMain b{font-size:25px;line-height:1;font-weight:900;letter-spacing:-.5px}.brandMain .ar{font-size:23px;font-weight:900;margin-top:3px;direction:rtl}.brandMain small{font-size:7.5px;font-weight:800;margin-top:3px}",
                        ".brandBox{display:grid;grid-template-rows:minmax(0,1fr) 9mm;min-width:0}.brandMain{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;min-width:0;overflow:hidden;padding:.7mm}.brandMain b{font-size:18px;line-height:1.05;font-weight:900;letter-spacing:-.3px;max-width:100%}.brandMain .ar{font-size:17px;line-height:1.05;font-weight:900;margin-top:2px;direction:rtl}.brandMain small{font-size:5.8px;line-height:1.05;font-weight:800;margin-top:2px;white-space:normal;max-width:100%}",
                    )
                    js = js.replace(
                        ".dateRow{border-top:1px solid #111;display:grid;grid-template-columns:29mm 1fr;align-items:center}.dateLabel{text-align:center;font-weight:900;font-size:11px}.dateLabel small{font-size:10px;margin-left:5px}.dateVal{text-align:center;font-weight:900;font-size:18px}",
                        ".dateRow{border-top:1px solid #111;display:grid;grid-template-columns:22mm minmax(0,1fr);align-items:center;min-width:0}.dateLabel{text-align:center;font-weight:900;font-size:8px;white-space:nowrap}.dateLabel small{font-size:7px;margin-left:2px}.dateVal{text-align:center;font-weight:900;font-size:13px;white-space:nowrap;overflow:hidden}",
                    )
                    js = js.replace(
                        ".qrBox{border-left:1px solid #111;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:1mm}.qrTitle{font-size:10.5px;font-weight:900}.qrNo{font-size:21px;font-weight:900;margin:1px 0}.qrBox img{width:27mm;height:27mm;object-fit:contain}",
                        ".qrBox{border-left:1px solid #111;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:.7mm;overflow:hidden}.qrTitle{font-size:7.5px;font-weight:900;white-space:nowrap}.qrNo{font-size:16px;font-weight:900;margin:1px 0}.qrBox img{width:21mm;height:21mm;object-fit:contain}",
                    )
                    js = js.replace("height:37mm}", "height:31mm}", 1)
                    js = js.replace("height:18.5mm}", "height:15.5mm}")
                    js = js.replace(
                        ".tripLabel{font-size:10px;font-weight:900;padding:1.3mm .7mm .5mm}.tripLabel span{direction:rtl;margin-left:4px}.tripVal{font-size:15px;font-weight:900;padding:.6mm 1mm;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
                        ".tripLabel{font-size:7.5px;line-height:1.05;font-weight:900;padding:1mm .4mm .3mm;white-space:nowrap;overflow:hidden}.tripLabel span{direction:rtl;margin-left:2px;font-size:7px}.tripVal{font-size:11.5px;font-weight:900;padding:.6mm .5mm;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
                    )
                    js = js.replace("height:7.2mm;padding:.7mm 1.2mm", "height:5.8mm;padding:.35mm .8mm")
                    js = js.replace("height:8.5mm;font-size:9.2px", "height:6.8mm;font-size:8px")
                    js = js.replace("height:8mm}.total", "height:6.2mm}.total")
                    js = js.replace("height:6.8mm;border-bottom", "height:5.4mm;border-bottom")
                    js = js.replace("margin-top:1.5mm;height:22mm", "margin-top:1mm;height:18mm")
                    js = js.replace("margin-top:1.5mm;height:24mm", "margin-top:1mm;height:18mm")
                    js = js.replace(
                        ".sheet{width:204mm;height:291mm;margin:0;padding:1mm 1.5mm;",
                        ".sheet{width:150mm;height:255mm;margin:0 auto;padding:1.5mm;",
                    )
                    return js
    raise RuntimeError("PRINT_TRIP_JS not found in printer_patch.py")


def _install_print_ui():
    print_js = _load_print_js()
    pattern = r"async function printTrip\(scna,mode\)\{.*?\n\}\n\n</script>"
    replacement = print_js + "\n\n</script>"
    updated, count = re.subn(pattern, lambda _m: replacement, core.HTML, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("SAMA printer patch could not find printTrip() in core.HTML")
    core.HTML = updated


def _install_exit_cash_save_fix():
    replacement = r'''window.saveMissingExitCash = async function(btn,scna,allowedTotal=0){
  const id='missingCash_'+String(scna).replace(/[^A-Za-z0-9_]/g,'_');
  const el=document.getElementById(id);
  if(!el){
    alert('Para giriş alanı bulunamadı. Sayfayı yenileyip tekrar deneyin.');
    return false;
  }

  const compact=String(el.value||'').trim().replace(/\s/g,'');
  let amount=0;
  if(/^\d{1,3}([.,]\d{3})+$/.test(compact)){
    amount=Number(compact.replace(/[.,]/g,''));
  }else if(/^\d+$/.test(compact)){
    amount=Number(compact);
  }else{
    amount=Number(compact.replace(/\./g,'').replace(',','.'));
  }

  if(!Number.isFinite(amount)||amount<=0){
    alert('Şoföre verilen toplam nakdi doğru girin. Örnek: 175000');
    el.focus();
    return false;
  }

  allowedTotal=Number(allowedTotal||0);
  if(allowedTotal>0 && amount>allowedTotal+0.01){
    alert('HATA: Girilen para gider toplamını aşıyor.\n\nGider toplamı: '+money(allowedTotal)+' IQD\nGirilen: '+money(amount)+' IQD');
    el.focus();
    return false;
  }

  const oldText=btn ? btn.textContent : 'NAKİT KAYDET';
  if(btn){btn.disabled=true;btn.textContent='KAYDEDİLİYOR...';}

  try{
    const resp=await fetch('/api/trips/'+encodeURIComponent(scna)+'/exit-cash',{
      method:'POST',
      credentials:'same-origin',
      headers:{'Content-Type':'application/json','Accept':'application/json'},
      body:JSON.stringify({amount:amount})
    });

    let data=null;
    try{data=await resp.json();}catch(_e){}
    if(!resp.ok){
      throw new Error((data&&data.detail)||('HTTP '+resp.status));
    }
    if(!data||data.ok!==true){
      throw new Error('Sunucudan kayıt onayı alınamadı.');
    }

    if(btn){btn.textContent='KAYDEDİLDİ ✓';}
    el.value=amount.toLocaleString('tr-TR');
    setTimeout(async()=>{
      try{await loadExitCashMissing();}catch(_e){}
      if(typeof loadCashControl==='function'){
        try{await loadCashControl();}catch(_e){}
      }
    },350);
    return false;
  }catch(e){
    if(btn){btn.disabled=false;btn.textContent=oldText;}
    alert('Kayıt yapılamadı: '+(e&&e.message?e.message:e));
    el.focus();
    return false;
  }
};

if(!window.__exitCashDelegatedBound){
  window.__exitCashDelegatedBound=true;
  document.addEventListener('click',function(ev){
    const btn=ev.target && ev.target.closest ? ev.target.closest('[data-exit-cash-save="1"]') : null;
    if(!btn)return;
    ev.preventDefault();
    ev.stopPropagation();
    const scna=btn.getAttribute('data-scna')||'';
    const allowed=Number(btn.getAttribute('data-allowed')||0);
    window.saveMissingExitCash(btn,scna,allowed);
  },true);
}

async function loadExit('''

    pattern = r"async function saveMissingExitCash\(scna,allowedTotal=0\)\{.*?\n\}\n\nasync function loadExit\("
    updated, count = re.subn(pattern, lambda _m: replacement, core.HTML, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Exit cash save patch could not find saveMissingExitCash() in core.HTML")

    original_button = '<button class="btn orange" onclick="saveMissingExitCash(\'${String(x.scna).replace(/\'/g,"\\\\\'")}\',Number(x.visible_expense_total||0))">Kaydet</button>'
    delegated_button = '<button type="button" class="btn orange" data-exit-cash-save="1" data-scna="${String(x.scna).replace(/&/g,\'&amp;\').replace(/\"/g,\'&quot;\')}" data-allowed="${Number(x.visible_expense_total||0)}">NAKİT KAYDET</button>'
    updated2 = updated.replace(original_button, delegated_button)

    updated2 = re.sub(
        r'<button[^>]*onclick="(?:return )?(?:window\.)?saveMissingExitCash\([^>]*>NAKİT KAYDET</button>',
        delegated_button,
        updated2,
        count=1,
    )

    core.HTML = updated2


_install_print_ui()
_install_exit_cash_save_fix()


@core.app.get("/api/print-entry-expenses/{scna}")
def print_entry_expenses(scna: str):
    key = str(scna or "").strip()
    c = core.db()
    try:
        trip = c.execute(
            """SELECT entry_extra_expense_1,entry_extra_expense_2,entry_extra_expense_3,entry_note
               FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))""",
            (key,),
        ).fetchone()
        fuels = c.execute(
            """SELECT liters,total,note FROM fuel_purchases
               WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) ORDER BY id""",
            (key,),
        ).fetchall()

        rows = []
        road_total = sum(float(r["total"] or 0) for r in fuels)
        road_liters = sum(float(r["liters"] or 0) for r in fuels)
        fuel_notes = [str(r["note"] or "").strip() for r in fuels if str(r["note"] or "").strip()]
        if road_total or road_liters or fuel_notes:
            rows.append([
                "10",
                "Road Fuel Expense (ENTRY)",
                "مصاريف وقود الطريق - الدخول",
                f"{road_liters:g} L" if road_liters else "-",
                road_total,
                "entryExpense",
                "; ".join(dict.fromkeys(fuel_notes)) or "Fuel purchased during trip",
            ])

        if trip:
            entry_note = str(trip["entry_note"] or "").strip()
            extras = [
                float(trip["entry_extra_expense_1"] or 0),
                float(trip["entry_extra_expense_2"] or 0),
                float(trip["entry_extra_expense_3"] or 0),
            ]
            no = 11
            for idx, amount in enumerate(extras, 1):
                if amount:
                    rows.append([
                        str(no),
                        f"Entry Extra Expense {idx}",
                        f"مصاريف دخول إضافية {idx}",
                        "-",
                        amount,
                        "entryExpense",
                        entry_note or "Entry expense",
                    ])
                    no += 1
        return {"ok": True, "rows": rows}
    finally:
        c.close()


@core.app.get("/api/print-qr/{scna}")
def print_qr(scna: str):
    import qrcode

    value = str(scna or "").strip().upper()
    img = qrcode.make(value)
    bio = BytesIO()
    img.save(bio, format="PNG")
    return Response(
        content=bio.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@core.app.get("/api/print-logo")
def print_logo():
    raw = (BASE / "nukhbat_logo_bw.b64").read_text(encoding="utf-8").strip()
    return Response(
        content=base64.b64decode(raw),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@core.app.get("/api/patch-version")
def patch_version():
    return {"ok": True, "version": "print-a4-header-fit-v5"}


app = core.app
