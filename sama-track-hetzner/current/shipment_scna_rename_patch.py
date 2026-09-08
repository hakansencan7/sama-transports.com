import sqlite3
from fastapi import Request, HTTPException

import kolaybi_return_extra_purchase_patch as base

app = base.app
core = base.core
kdb = base.kdb
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _qident(name):
    return '"' + str(name).replace('"', '""') + '"'


def _table_columns(c, table):
    return {str(r['name']) for r in c.execute(f'PRAGMA table_info({_qident(table)})').fetchall()}


def _kolaybi_sent_for_scna(scna):
    """Never rename an SCNA silently after a KolayBi document was really sent.

    The remote invoice serial cannot be renamed by changing SAMA SQLite. Blocking here
    prevents local history from claiming a remote document has a different serial.
    """
    c = kdb()
    try:
        tables = {str(r['name']) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        hits = []
        for table in ('sent_documents_v2', 'sent_documents'):
            if table not in tables:
                continue
            cols = _table_columns(c, table)
            if 'scna' not in cols:
                continue
            rows = c.execute(
                f'''SELECT * FROM {_qident(table)} WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) LIMIT 10''',
                (_txt(scna),)
            ).fetchall()
            for row in rows:
                x = dict(row)
                hits.append({
                    'table': table,
                    'kind': _txt(x.get('doc_kind')),
                    'document_id': _txt(x.get('document_id')),
                })
        return hits
    finally:
        c.close()


def _migrate_kolaybi_local_overrides(old_scna, new_scna):
    """Move only unsent local choices/metadata; never rewrite remote-send history."""
    warnings = []
    moved = []
    c = kdb()
    try:
        tables = {str(r['name']) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table in ('sale_contact_overrides', 'invoice_metadata_overrides'):
            if table not in tables:
                continue
            cols = _table_columns(c, table)
            if 'scna' not in cols:
                continue
            old_count = int(c.execute(
                f'''SELECT COUNT(*) n FROM {_qident(table)} WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',
                (_txt(old_scna),)
            ).fetchone()['n'] or 0)
            if not old_count:
                continue
            target_count = int(c.execute(
                f'''SELECT COUNT(*) n FROM {_qident(table)} WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',
                (_txt(new_scna),)
            ).fetchone()['n'] or 0)
            if target_count:
                warnings.append(f'{table}: yeni SCNA için mevcut yerel KolayBi ayarı var; eski ayar taşınmadı.')
                continue
            c.execute(
                f'''UPDATE {_qident(table)} SET scna=? WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',
                (_txt(new_scna), _txt(old_scna))
            )
            moved.append(table)
        c.commit()
    except Exception as e:
        c.rollback()
        warnings.append('KolayBi yerel seçimleri taşınamadı: ' + str(e))
    finally:
        c.close()
    return moved, warnings


@app.post('/api/trips/{old_scna}/rename-scna')
async def rename_trip_scna(old_scna: str, request: Request):
    body = await request.json()
    old_key = core._normalize_scna_value(old_scna)
    ok, new_or_error = core._validate_scna_value(body.get('new_scna'))
    if not ok:
        raise HTTPException(status_code=400, detail=new_or_error)
    new_key = new_or_error

    if old_key.upper() == new_key.upper():
        return {'ok': True, 'old_scna': old_key, 'new_scna': new_key, 'changed': False, 'updated_tables': []}

    sent = _kolaybi_sent_for_scna(old_key)
    if sent:
        info = ', '.join(
            (x.get('kind') or 'DOC') + (f" #{x.get('document_id')}" if x.get('document_id') else '')
            for x in sent[:5]
        )
        raise HTTPException(
            status_code=409,
            detail=(
                'Bu SCNA için KolayBi’ye daha önce gerçek belge gönderilmiş. '
                'Remote serial otomatik değiştirilemez; SCNA düzeltmesi güvenlik için durduruldu. '
                + (f'Belgeler: {info}' if info else '')
            )
        )

    c = core.db()
    updated_tables = []
    try:
        old_row = c.execute(
            '''SELECT id,scna FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) LIMIT 1''',
            (old_key,)
        ).fetchone()
        if not old_row:
            raise HTTPException(status_code=404, detail='Düzeltilecek SCNA bulunamadı.')
        stored_old = _txt(old_row['scna'])

        duplicate = c.execute(
            '''SELECT id,scna FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) AND id<>? LIMIT 1''',
            (new_key, old_row['id'])
        ).fetchone()
        if duplicate:
            raise HTTPException(status_code=409, detail=f'Yeni SCNA zaten kayıtlı: {duplicate["scna"]}')

        c.execute('BEGIN IMMEDIATE')
        table_rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

        # Update every shipment-domain table that literally keys rows by SCNA. This
        # catches fuel, return expenses, audit history, QR/status tables and future
        # additive patch tables instead of maintaining a fragile hard-coded list.
        for tr in table_rows:
            table = str(tr['name'])
            if table == 'trips':
                continue
            cols = _table_columns(c, table)
            if 'scna' not in cols:
                continue
            cur = c.execute(
                f'''UPDATE {_qident(table)} SET scna=? WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',
                (new_key, stored_old)
            )
            if int(cur.rowcount or 0) > 0:
                updated_tables.append({'table': table, 'rows': int(cur.rowcount or 0)})

        c.execute(
            '''UPDATE trips SET scna=?,manual_lock=1,manual_lock_at=DATETIME('now','localtime'),
                   manual_lock_reason='SCNA numarası düzeltildi',updated_at=CURRENT_TIMESTAMP
               WHERE id=?''',
            (new_key, old_row['id'])
        )
        updated_tables.append({'table': 'trips', 'rows': 1})
        c.commit()
    except HTTPException:
        c.rollback()
        raise
    except sqlite3.IntegrityError as e:
        c.rollback()
        raise HTTPException(status_code=409, detail='SCNA değişikliği ilişkili bir kayıtla çakıştı: ' + str(e))
    except Exception as e:
        c.rollback()
        raise HTTPException(status_code=500, detail='SCNA değiştirilemedi: ' + str(e))
    finally:
        c.close()

    moved, warnings = _migrate_kolaybi_local_overrides(stored_old, new_key)
    try:
        core.audit(
            'SCNA_RENAME', new_key, f'SCNA düzeltildi: {stored_old} → {new_key}',
            'SEVKIYAT', stored_old, new_key
        )
    except Exception as e:
        warnings.append('Audit kaydı yazılamadı: ' + str(e))

    return {
        'ok': True,
        'changed': True,
        'old_scna': stored_old,
        'new_scna': new_key,
        'updated_tables': updated_tables,
        'kolaybi_local_moved': moved,
        'warnings': warnings,
    }


# Add SCNA correction directly to the existing Edit Center. No extra <script> block.
edit_anchor = '''<div class="grid" style="margin-top:14px">
        <div class="field"><label>Plaka</label><input id="ePlate" value="${editCx.plate||''}"></div>'''
edit_replacement = '''<div class="grid" style="margin-top:14px">
        <div class="field"><label>SCNA / SERIAL NO</label><input id="eScna" value="${String(editCx.scna||scna).replace(/"/g,'&quot;')}" autocomplete="off"></div>
        <div class="field"><label>SCNA DÜZELTME</label><button type="button" class="btn orange" onclick="renameScnaEdit()">SCNA NUMARASINI DÜZELT</button><span class="small">Yanlış yazılan SCNA'yı ilişkili sevkiyat kayıtlarıyla birlikte taşır.</span></div>
        <div class="field"><label>Plaka</label><input id="ePlate" value="${editCx.plate||''}"></div>'''
if edit_anchor in html and 'id="eScna"' not in html:
    html = html.replace(edit_anchor, edit_replacement, 1)

rename_helper = r'''
async function renameScnaEdit(){
  const oldScna=String(editScna?.value||'').trim().toUpperCase();
  const newScna=String(document.getElementById('eScna')?.value||'').trim().toUpperCase();
  if(!oldScna||!newScna){alert('Eski ve yeni SCNA gerekli.');return;}
  if(oldScna===newScna){alert('SCNA değişmedi.');return;}
  if(!confirm('SCNA numarası düzeltilecek:\n\n'+oldScna+'  →  '+newScna+'\n\nYakıt, dönüş giderleri ve SCNA ile bağlı operasyon kayıtları da yeni numaraya taşınacak. Emin misin?'))return;
  const box=document.getElementById('editValidation');
  if(box){box.style.display='block';box.innerHTML='<b>SCNA DÜZELTİLİYOR...</b>';}
  try{
    const r=await api('/api/trips/'+encodeURIComponent(oldScna)+'/rename-scna',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_scna:newScna})
    });
    editScna.value=r.new_scna||newScna;
    if(box)box.innerHTML='<b style="color:#166534">✓ SCNA DÜZELTİLDİ: '+oldScna+' → '+(r.new_scna||newScna)+'</b>'+(r.warnings?.length?'<br>'+r.warnings.map(x=>typeof kbEsc==='function'?kbEsc(x):String(x)).join('<br>'):'');
    await loadEditCenter();
    try{await loadTrips();}catch(_e){}
    try{await loadQuality();}catch(_e){}
  }catch(e){
    if(box)box.innerHTML='<b style="color:#991b1b">'+String(e.message||e)+'</b>';
    alert(e.message||e);
  }
}
'''
marker = 'function editPayload(){'
if marker in html and 'async function renameScnaEdit' not in html:
    html = html.replace(marker, rename_helper + '\n' + marker, 1)

# Prevent the ordinary data-save button from silently ignoring a changed SCNA field.
old_validate = '''async function validateAndSaveEdit(){
  const scna=(editScna.value||'').trim().toUpperCase();
  if(!scna) return;'''
new_validate = '''async function validateAndSaveEdit(){
  const scna=(editScna.value||'').trim().toUpperCase();
  if(!scna) return;
  const requestedScna=String(document.getElementById('eScna')?.value||scna).trim().toUpperCase();
  if(requestedScna!==scna){
    alert('SCNA alanını değiştirdin. Önce “SCNA NUMARASINI DÜZELT” butonuna bas; normal kayıt butonu SCNA değişikliğini sessizce atlamaz.');
    return;
  }'''
if old_validate in html:
    html = html.replace(old_validate, new_validate, 1)

core.HTML = html
print('[SAMA] Shipment SCNA rename active: Edit Center can safely migrate an incorrect SCNA and dependent shipment rows')
