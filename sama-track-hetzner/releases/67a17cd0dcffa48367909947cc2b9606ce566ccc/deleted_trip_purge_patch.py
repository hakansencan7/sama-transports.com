import sqlite3
from fastapi import Request, HTTPException

import shipment_edit_money_patch as base

app = base.app
core = base.core
html = core.HTML


def _qident(name):
    return '"' + str(name).replace('"', '""') + '"'


def _cols(c, table):
    return {str(r['name']) for r in c.execute(f'PRAGMA table_info({_qident(table)})').fetchall()}


def _is_financial_history_table(table):
    """Keep independent accounting/audit history even when a shipment itself is purged."""
    t = str(table or '').lower()
    if t in {'audit_log', 'advances', 'advance_settlements'}:
        return True
    protected_tokens = (
        'audit', 'advance', 'cash', 'ledger', 'account', 'payment',
        'invoice', 'kolaybi', 'sent_document', 'general_expense', 'daily_expense'
    )
    return any(x in t for x in protected_tokens)


@app.delete('/api/trips/{scna}/purge')
def purge_deleted_trip(scna: str, request: Request):
    user = core._request_user(request)
    if not user or str(user.get('role') or '').upper() != 'ADMIN':
        raise HTTPException(403, 'Sadece ADMIN kalıcı silebilir.')

    key = str(scna or '').strip()
    if not key:
        raise HTTPException(400, 'SCNA gerekli.')

    c = core.db()
    deleted_children = []
    stored_scna = key
    try:
        row = c.execute(
            '''SELECT id,scna,is_deleted FROM trips
               WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) LIMIT 1''',
            (key,)
        ).fetchone()
        if not row:
            raise HTTPException(404, 'Silinecek sevkiyat bulunamadı.')
        if int(row['is_deleted'] or 0) != 1:
            raise HTTPException(409, 'Aktif sevkiyat doğrudan kalıcı silinemez. Önce geri dönüşüme gönderin.')

        stored_scna = str(row['scna'] or key).strip()
        c.execute('BEGIN IMMEDIATE')

        tables = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for tr in tables:
            table = str(tr['name'])
            if table == 'trips' or _is_financial_history_table(table):
                continue
            try:
                cols = _cols(c, table)
            except Exception:
                continue
            if 'scna' not in cols:
                continue
            cur = c.execute(
                f'''DELETE FROM {_qident(table)}
                    WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',
                (stored_scna,)
            )
            if int(cur.rowcount or 0) > 0:
                deleted_children.append({'table': table, 'rows': int(cur.rowcount or 0)})

        cur = c.execute('DELETE FROM trips WHERE id=? AND is_deleted=1', (row['id'],))
        if int(cur.rowcount or 0) != 1:
            raise HTTPException(409, 'Sevkiyat kalıcı silinemedi; kayıt durumu değişmiş olabilir.')
        c.commit()
    except HTTPException:
        c.rollback()
        raise
    except sqlite3.IntegrityError as e:
        c.rollback()
        raise HTTPException(409, 'Kalıcı silme ilişkili kayıt nedeniyle tamamlanamadı: ' + str(e))
    except Exception as e:
        c.rollback()
        raise HTTPException(500, 'Kalıcı silme hatası: ' + str(e))
    finally:
        c.close()

    try:
        core.audit(
            'PURGE_DELETE', stored_scna,
            'Geri dönüşümdeki sevkiyat ADMIN tarafından kalıcı silindi. Sevkiyat alt kayıtları temizlendi; muhasebe/audit geçmişi korundu.',
            'SEVKIYAT'
        )
    except Exception:
        pass

    return {'ok': True, 'scna': stored_scna, 'deleted_children': deleted_children}


old_loader = r'''async function loadDeletedTrips(){
  if(!AUTH_USER||AUTH_USER.role!=='ADMIN')return;
  const d=await api('/api/trips-deleted'); deletedRows.innerHTML=d.map(x=>`<tr><td><b>${x.scna}</b></td><td>${x.plate||''}</td><td>${fmtDateTime(x.deleted_at)}</td><td>${x.deleted_by||''}</td><td>${Math.max(0,Number(x.days_left||0))}</td><td>${Number(x.days_left||0)>=0?`<button class="btn green" onclick="restoreTrip('${x.scna}')">Geri Al</button>`:'Süre Doldu'}</td></tr>`).join('');
}
async function restoreTrip(scna){await api('/api/trips/'+encodeURIComponent(scna)+'/restore',{method:'POST'});await loadDeletedTrips();}'''

new_loader = r'''async function loadDeletedTrips(){
  if(!AUTH_USER||AUTH_USER.role!=='ADMIN')return;
  const d=await api('/api/trips-deleted');
  deletedRows.innerHTML=d.map(x=>`<tr>
    <td><b>${x.scna}</b></td><td>${x.plate||''}</td><td>${fmtDateTime(x.deleted_at)}</td><td>${x.deleted_by||''}</td>
    <td>${Math.max(0,Number(x.days_left||0))}</td>
    <td style="display:flex;gap:6px;flex-wrap:wrap">
      ${Number(x.days_left||0)>=0?`<button class="btn green" onclick="restoreTrip('${x.scna}')">GERİ AL</button>`:''}
      <button class="btn danger" onclick="purgeDeletedTrip('${x.scna}')">KALICI SİL</button>
    </td></tr>`).join('');
}
async function restoreTrip(scna){
  await api('/api/trips/'+encodeURIComponent(scna)+'/restore',{method:'POST'});
  await loadDeletedTrips();
}
async function purgeDeletedTrip(scna){
  const key=String(scna||'').trim();
  if(!key)return;
  if(!confirm(key+' kalıcı olarak silinecek.\n\nBu sevkiyat geri alınamaz. Aynı SCNA daha sonra yeniden oluşturulabilir.\n\nKalıcı silinsin mi?'))return;
  try{
    await api('/api/trips/'+encodeURIComponent(key)+'/purge',{method:'DELETE'});
    await loadDeletedTrips();
    try{await loadTrips();}catch(_e){}
    try{await loadDash();}catch(_e){}
  }catch(e){alert(e.message||e);}
}'''

if old_loader in html:
    html = html.replace(old_loader, new_loader, 1)

old_note = '<span class="section-note">7 gün içinde geri alınabilir.</span>'
new_note = '<span class="section-note">7 gün içinde geri alınabilir. İsterseniz KALICI SİL ile beklemeden tamamen silebilirsiniz.</span>'
if old_note in html:
    html = html.replace(old_note, new_note, 1)

core.HTML = html
print('[SAMA] Deleted shipment permanent purge active: ADMIN can permanently delete immediately from recycle list')

# Final browser-scope repair: Entry OTHER must use lexical `cx`, not window.cx,
# otherwise the form can display OTHER values without persisting them for print/KolayBi.
import entry_other_scna_scope_fix_patch as entry_other_scna_scope_fix
