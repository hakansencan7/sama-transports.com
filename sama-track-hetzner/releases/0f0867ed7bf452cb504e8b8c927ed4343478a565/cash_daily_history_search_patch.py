from fastapi import HTTPException
import re

# Full-history search for the SAMA Daily Cash / Daily Expense screen.
# Backend reads muhasebe.db through core.db()'s accounting redirection.
# UI helper is injected into the EXISTING main script only; no extra <script> block.
import kolaybi_daily_expense_audit_bridge_patch as base

app = base.app
core = base.core
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _q(name):
    return '"' + str(name).replace('"', '""') + '"'


def _cols(c):
    try:
        return [str(r['name']) for r in c.execute('PRAGMA table_info(cash_daily_expenses)').fetchall()]
    except Exception:
        return []


def _pick(cols, *names):
    for name in names:
        if name in cols:
            return name
    return ''


def _parse_amount_query(v):
    s = _txt(v).replace('\u00a0', '').replace(' ', '')
    if not s or not re.fullmatch(r'[-+0-9.,]+', s):
        return None
    try:
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            right = s.rsplit(',', 1)[1]
            s = s.replace('.', '')
            s = s.replace(',', '.' if len(right) <= 2 else '')
        elif '.' in s:
            parts = s.split('.')
            if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
                s = ''.join(parts)
        return float(s)
    except Exception:
        return None


@app.get('/api/cash-control/history-search')
def cash_daily_history_search(q: str = '', limit: int = 300):
    term = _txt(q)
    if not term:
        raise HTTPException(status_code=400, detail='Arama kelimesi boş olamaz.')
    if len(term) > 200:
        raise HTTPException(status_code=400, detail='Arama metni çok uzun.')
    limit = max(1, min(int(limit or 300), 500))

    c = core.db()
    try:
        cols = _cols(c)
        if not cols:
            return {'ok': True, 'query': term, 'count': 0, 'rows': [], 'message': 'Günlük Kasa tablosu boş.'}

        # Search every stored column so old records remain discoverable even if the
        # schema gained fields over time. SQLite CAST makes IDs, dates and amounts searchable too.
        text_parts = [f"UPPER(COALESCE(CAST({_q(col)} AS TEXT),'')) LIKE UPPER(?)" for col in cols]
        params = [f'%{term}%'] * len(text_parts)

        amount_col = _pick(cols, 'amount', 'total', 'total_amount', 'expense_amount')
        amount_query = _parse_amount_query(term)
        if amount_col and amount_query is not None:
            text_parts.append(f'ABS(COALESCE(CAST({_q(amount_col)} AS REAL),0)-?) < 0.011')
            params.append(amount_query)

        where = '(' + ' OR '.join(text_parts) + ')'
        # Respect common soft-delete flags while still searching every historical date.
        if 'deleted_at' in cols:
            where += " AND COALESCE(deleted_at,'')=''"
        if 'is_deleted' in cols:
            where += ' AND COALESCE(is_deleted,0)=0'
        if 'active' in cols:
            where += ' AND COALESCE(active,1)<>0'

        date_col = _pick(cols, 'expense_date', 'document_date', 'date', 'created_at', 'updated_at')
        id_col = _pick(cols, 'id')
        order_parts = []
        if date_col:
            order_parts.append(f'{_q(date_col)} DESC')
        if id_col:
            order_parts.append(f'{_q(id_col)} DESC')
        order_sql = ','.join(order_parts) if order_parts else 'rowid DESC'

        sql = f'SELECT * FROM cash_daily_expenses WHERE {where} ORDER BY {order_sql} LIMIT ?'
        params.append(limit + 1)
        raw = c.execute(sql, tuple(params)).fetchall()
        truncated = len(raw) > limit
        raw = raw[:limit]

        document_col = _pick(cols, 'document_no', 'serial_no', 'invoice_no', 'invoice_number', 'document_number', 'doc_no')
        currency_col = _pick(cols, 'currency', 'currency_code')
        note_col = _pick(cols, 'note', 'description', 'expense_note')
        created_col = _pick(cols, 'created_at')
        updated_col = _pick(cols, 'updated_at')

        rows = []
        for row in raw:
            d = dict(row)
            try:
                amount = float(d.get(amount_col) or 0) if amount_col else 0.0
            except Exception:
                amount = 0.0
            rows.append({
                'id': d.get(id_col) if id_col else None,
                'document_no': _txt(d.get(document_col)) if document_col else '',
                'amount': amount,
                'currency': _txt(d.get(currency_col)) if currency_col else '',
                'expense_date': _txt(d.get(date_col)) if date_col else '',
                'note': _txt(d.get(note_col)) if note_col else '',
                'created_at': _txt(d.get(created_col)) if created_col else '',
                'updated_at': _txt(d.get(updated_col)) if updated_col else '',
            })

        return {
            'ok': True,
            'query': term,
            'count': len(rows),
            'truncated': truncated,
            'limit': limit,
            'rows': rows,
            'message': f'{len(rows)} geçmiş Günlük Kasa kaydı bulundu.' + (' İlk 500 sonuç gösteriliyor.' if truncated else ''),
        }
    finally:
        c.close()


helper = r'''
function samaCashNorm(v){
  return String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();
}
function samaCashEsc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function samaCashMoney(v){return Number(v||0).toLocaleString('tr-TR',{maximumFractionDigits:2});}
function samaCashVisible(el){return !!(el && el.isConnected && el.getClientRects().length && getComputedStyle(el).display!=='none');}
function samaCashFindHost(){
  const els=[...document.querySelectorAll('h1,h2,h3,h4,.page-title,.section-title,.card-title,strong,b,section,main,.page,.view,.content,.card,div')];
  const hits=els.filter(el=>{
    if(!samaCashVisible(el) || el.closest('nav,aside'))return false;
    const t=samaCashNorm(el.innerText||el.textContent||'');
    return t.includes('GUNLUK KASA') || t.includes('DAILY CASH');
  });
  if(!hits.length)return null;
  hits.sort((a,b)=>(a.innerText||'').length-(b.innerText||'').length);
  let hit=hits[0];
  // Prefer a practical content container rather than only the title node.
  const host=hit.closest('section,.page,.view,.content,.card') || hit.parentElement || hit;
  return host;
}
function samaCashSearchAttach(){
  if(document.getElementById('samaCashHistorySearch'))return;
  const host=samaCashFindHost();if(!host)return;
  const box=document.createElement('div');
  box.id='samaCashHistorySearch';
  box.style.cssText='margin:10px 0 14px;padding:12px;border:1px solid rgba(128,128,128,.25);border-radius:12px;background:rgba(128,128,128,.06)';
  box.innerHTML=`
    <div style="display:flex;gap:8px;align-items:end;flex-wrap:wrap">
      <div style="min-width:280px;flex:1">
        <label style="display:block;font-size:12px;font-weight:700;margin-bottom:5px">TÜM GEÇMİŞTE ARA</label>
        <input id="samaCashHistoryQ" type="text" placeholder="Belge no, açıklama, tutar, tarih, para birimi..." style="width:100%" />
      </div>
      <button class="btn primary" type="button" onclick="samaCashHistoryRun()">ARA</button>
      <button class="btn secondary" type="button" onclick="samaCashHistoryClear()">TEMİZLE</button>
    </div>
    <div id="samaCashHistoryState" class="section-note" style="margin-top:6px">Bugünle sınırlı değil. Muhasebe DB içindeki tüm geçmiş Günlük Kasa kayıtlarında arar.</div>
    <div id="samaCashHistoryResult" style="display:none;overflow:auto;max-height:520px;margin-top:10px"></div>`;
  const first=host.firstElementChild;
  if(first)host.insertBefore(box, first.nextSibling);else host.prepend(box);
  const inp=document.getElementById('samaCashHistoryQ');
  if(inp)inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();samaCashHistoryRun();}});
}
async function samaCashHistoryRun(){
  const inp=document.getElementById('samaCashHistoryQ'),state=document.getElementById('samaCashHistoryState'),out=document.getElementById('samaCashHistoryResult');
  const q=String(inp?.value||'').trim();if(!q){if(inp)inp.focus();return;}
  if(state)state.textContent='TÜM GEÇMİŞ ARANIYOR...';
  try{
    const r=await api('/api/cash-control/history-search?q='+encodeURIComponent(q)+'&limit=500');
    if(state)state.innerHTML='<b>'+Number(r.count||0).toLocaleString('tr-TR')+' kayıt bulundu.</b>'+(r.truncated?' İlk 500 sonuç gösteriliyor.':'');
    const rows=r.rows||[];
    if(!rows.length){if(out){out.style.display='block';out.innerHTML='<div class="section-note">SONUÇ YOK</div>';}return;}
    let body=rows.map(x=>`<tr>
      <td>${samaCashEsc(x.expense_date||x.created_at||'-')}</td>
      <td><b>${samaCashEsc(x.document_no||'-')}</b></td>
      <td style="text-align:right"><b>${samaCashMoney(x.amount)}</b> ${samaCashEsc(x.currency||'')}</td>
      <td>${samaCashEsc(x.note||'-')}</td>
      <td>${samaCashEsc(x.id??'-')}</td>
    </tr>`).join('');
    if(out){out.style.display='block';out.innerHTML=`<table style="width:100%;border-collapse:collapse"><thead><tr><th>TARİH</th><th>BELGE NO</th><th>TUTAR</th><th>AÇIKLAMA</th><th>ID</th></tr></thead><tbody>${body}</tbody></table>`;}
  }catch(e){if(state)state.innerHTML='<span class="kb-missing">'+samaCashEsc(e.message||e)+'</span>';if(out)out.style.display='none';}
}
function samaCashHistoryClear(){
  const inp=document.getElementById('samaCashHistoryQ'),state=document.getElementById('samaCashHistoryState'),out=document.getElementById('samaCashHistoryResult');
  if(inp){inp.value='';inp.focus();}if(out){out.innerHTML='';out.style.display='none';}
  if(state)state.textContent='Bugünle sınırlı değil. Muhasebe DB içindeki tüm geçmiş Günlük Kasa kayıtlarında arar.';
}
function samaCashSearchBoot(){
  setTimeout(samaCashSearchAttach,250);
  if(!window.__samaCashSearchObserver && document.body){
    window.__samaCashSearchObserver=new MutationObserver(()=>samaCashSearchAttach());
    window.__samaCashSearchObserver.observe(document.body,{childList:true,subtree:true});
  }
  if(!window.__samaCashSearchClick){
    window.__samaCashSearchClick=true;
    document.addEventListener('click',e=>{
      const t=samaCashNorm(e.target?.innerText||e.target?.textContent||'');
      if(t.includes('GUNLUK KASA')||t.includes('DAILY CASH'))setTimeout(samaCashSearchAttach,180);
    },true);
  }
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',samaCashSearchBoot);else samaCashSearchBoot();
'''

# Safe existing-JS insertion. This anchor is already part of the final KolayBi/SAMA script chain.
marker = 'async function kbLoadSingleV2(){'
inserted = False
if marker in html and 'function samaCashHistoryRun' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)
    inserted = True

core.HTML = html
print(f'[SAMA] Daily Cash full-history search active: js={1 if inserted else 0}; searches all cash_daily_expenses dates in muhasebe.db')
