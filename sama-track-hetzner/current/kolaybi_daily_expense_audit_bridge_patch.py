from fastapi import HTTPException

# One-click bridge from SAMA Daily Expense records into the existing KolayBi
# accounting-audit screen. No KolayBi API call is made here; it only prepares
# SERIAL + EXPECTED AMOUNT rows from muhasebe.db, then the existing local audit
# snapshot performs the comparison.
import kolaybi_general_expense_v1_read_patch as base
import kolaybi_bulk_accounting_audit_patch as audit

app = base.app
core = base.core
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _columns(c, table):
    try:
        return {str(r['name']) for r in c.execute(f'PRAGMA table_info({table})').fetchall()}
    except Exception:
        return set()


def _pick(cols, *names):
    for name in names:
        if name in cols:
            return name
    return ''


@app.get('/api/kolaybi/accounting-audit/daily-expenses')
def kb_audit_daily_expenses(date_from: str = '', date_to: str = ''):
    # Keep the original accountant-control rule: comparison uses the already
    # downloaded local KolayBi snapshot. This button must not silently refresh it.
    state = audit._audit_state()
    if not state.get('ready'):
        raise HTTPException(status_code=409, detail='MUHASEBE DB henüz hazır değil. Önce MUHASEBE DB YENİLE.')

    c = core.db()
    try:
        cols = _columns(c, 'cash_daily_expenses')
        if not cols:
            return {
                'ok': True, 'count': 0, 'rows': [], 'text': '',
                'message': 'Günlük Gider tablosunda kayıt bulunamadı.'
            }

        serial_col = _pick(cols, 'document_no', 'serial_no', 'invoice_no', 'invoice_number', 'document_number', 'doc_no')
        amount_col = _pick(cols, 'amount', 'total', 'total_amount', 'expense_amount')
        date_col = _pick(cols, 'expense_date', 'document_date', 'date', 'created_at')
        currency_col = _pick(cols, 'currency', 'currency_code')
        note_col = _pick(cols, 'note', 'description', 'expense_note')
        id_col = _pick(cols, 'id')

        if not serial_col or not amount_col:
            raise HTTPException(
                status_code=500,
                detail='Günlük Gider tablosunda belge no veya tutar alanı bulunamadı. '
                       f'Mevcut kolonlar: {", ".join(sorted(cols))}'
            )

        select_cols = []
        for col in (id_col, serial_col, amount_col, date_col, currency_col, note_col):
            if col and col not in select_cols:
                select_cols.append(col)

        where = [f"TRIM(COALESCE({serial_col},''))<>''", f'COALESCE({amount_col},0)<>0']
        params = []
        if date_col and _txt(date_from):
            where.append(f'DATE({date_col})>=DATE(?)')
            params.append(_txt(date_from)[:10])
        if date_col and _txt(date_to):
            where.append(f'DATE({date_col})<=DATE(?)')
            params.append(_txt(date_to)[:10])

        # Respect common soft-delete conventions when present.
        if 'deleted_at' in cols:
            where.append("COALESCE(deleted_at,'')=''")
        if 'is_deleted' in cols:
            where.append('COALESCE(is_deleted,0)=0')
        if 'active' in cols:
            where.append('COALESCE(active,1)<>0')

        order = date_col or id_col or serial_col
        sql = (
            'SELECT ' + ','.join(select_cols) + ' FROM cash_daily_expenses WHERE ' +
            ' AND '.join(where) + f' ORDER BY {order} ASC LIMIT 5001'
        )
        raw_rows = c.execute(sql, tuple(params)).fetchall()
        if len(raw_rows) > 5000:
            raise HTTPException(
                status_code=400,
                detail='Günlük Gider 5000 satırı aşıyor. Tarih aralığı seçip tekrar dene.'
            )

        out = []
        text_lines = []
        for r in raw_rows:
            d = dict(r)
            serial = _txt(d.get(serial_col))
            try:
                amount = float(d.get(amount_col) or 0)
            except Exception:
                amount = 0.0
            if not serial or amount == 0:
                continue
            rec = {
                'id': d.get(id_col) if id_col else None,
                'serial': serial,
                'amount': amount,
                'expense_date': _txt(d.get(date_col)) if date_col else '',
                'currency': _txt(d.get(currency_col)) if currency_col else '',
                'note': _txt(d.get(note_col)) if note_col else '',
            }
            out.append(rec)
            # Existing bulk parser reads TAB-delimited SERIAL + amount safely.
            text_lines.append(f'{serial}\t{amount:.2f}')

        return {
            'ok': True,
            'count': len(out),
            'rows': out,
            'text': '\n'.join(text_lines),
            'date_from': _txt(date_from)[:10],
            'date_to': _txt(date_to)[:10],
            'message': f'{len(out)} Günlük Gider kaydı KolayBi kontrolüne hazırlandı.',
        }
    finally:
        c.close()


# Add the bridge controls inside the existing audit card. No new <script> block.
button_anchor = '<button class="btn secondary" onclick="kbAuditRefresh()">MUHASEBE DB YENİLE</button>'
daily_controls = r'''
        <button class="btn secondary" onclick="kbAuditLoadDailyExpenses()">GÜNLÜK GİDERDEN ÇEK + KONTROL ET</button>
'''
if button_anchor in html and 'GÜNLÜK GİDERDEN ÇEK + KONTROL ET' not in html:
    html = html.replace(button_anchor, button_anchor + '\n' + daily_controls, 1)

textarea_anchor = '<textarea id="kbAuditInput"'
date_controls = r'''
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:9px">
      <div class="field"><label>GÜNLÜK GİDER TARİH BAŞLANGIÇ</label><input id="kbAuditDailyFrom" type="date"></div>
      <div class="field"><label>GÜNLÜK GİDER TARİH BİTİŞ</label><input id="kbAuditDailyTo" type="date"></div>
      <div class="section-note">Tarihleri boş bırakırsan tüm Günlük Gider kayıtları alınır. KolayBi DB ayrıca yenilenmez; mevcut snapshot ile kontrol edilir.</div>
    </div>
'''
if textarea_anchor in html and 'id="kbAuditDailyFrom"' not in html:
    html = html.replace(textarea_anchor, date_controls + '\n    ' + textarea_anchor, 1)

helper = r'''
async function kbAuditLoadDailyExpenses(){
  const inp=document.getElementById('kbAuditInput');
  const sum=document.getElementById('kbAuditSummary');
  const from=String(document.getElementById('kbAuditDailyFrom')?.value||'');
  const to=String(document.getElementById('kbAuditDailyTo')?.value||'');
  if(sum){sum.style.display='block';sum.textContent='GÜNLÜK GİDER KAYITLARI ALINIYOR...';}
  try{
    const q=new URLSearchParams();if(from)q.set('date_from',from);if(to)q.set('date_to',to);
    const r=await api('/api/kolaybi/accounting-audit/daily-expenses'+(q.toString()?'?'+q.toString():''));
    if(!r.count){
      if(inp)inp.value='';
      if(sum)sum.innerHTML='<span class="kb-missing">GÜNLÜK GİDERDEN KONTROL EDİLECEK BELGE BULUNAMADI.</span>';
      return;
    }
    if(inp)inp.value=String(r.text||'');
    if(sum)sum.innerHTML='<span class="kb-ready">✓ '+Number(r.count||0).toLocaleString('tr-TR')+' GÜNLÜK GİDER KAYDI ALINDI.</span> &nbsp; KolayBi snapshot ile karşılaştırılıyor...';
    await kbAuditCheck();
  }catch(e){
    if(sum)sum.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';
    alert(e.message||e);
  }
}
'''
marker = 'async function kbAuditRefresh(){'
if marker in html and 'async function kbAuditLoadDailyExpenses' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

core.HTML = html
print('[SAMA] Daily Expense -> KolayBi audit bridge active: one-click local pull + amount comparison, no automatic API refresh')
