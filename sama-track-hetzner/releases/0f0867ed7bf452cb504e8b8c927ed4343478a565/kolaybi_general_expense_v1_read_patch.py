import time

import kolaybi_general_expense_scope_fix_patch as previous
import kolaybi_bulk_accounting_audit_patch as audit
import kolaybi_serial_dual_kind_snapshot_patch as dual

app = previous.app
core = previous.core
html = core.HTML

PAGE_SIZE = audit.AUDIT_PAGE_SIZE
MAX_PAGES = audit.AUDIT_MAX_PAGES
PAGE_DELAY = audit.AUDIT_PAGE_DELAY


def _txt(v):
    return str(v or '').strip()


def _type_text(row):
    if not isinstance(row, dict):
        return ''
    vals = []
    for key in ('type', 'commercial_doc_type', 'document_type', 'invoice_type', 'type_key', 'type_group'):
        v = audit._wide_value(row, (key,))
        if v:
            vals.append(_txt(v).lower())
    return ' '.join(vals).replace('-', '_')


def _wrong_kind(row):
    t = _type_text(row)
    if not t:
        return False
    if 'general_expense' in t or ('general' in t and 'expense' in t):
        return False
    return any(x in t for x in (
        'sale_invoice', 'purchase_invoice', 'sale_return_invoice', 'purchase_return_invoice',
        'sale_waybill', 'purchase_waybill', 'self_employment_receipt'
    ))


def _scan(params_base, label):
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        params = {**params_base, 'page': page, 'per_page': PAGE_SIZE}
        try:
            rows = dual.rate._one_get(params)
        except Exception as e:
            if page == 1:
                return [], f'{label}: {e}'
            raise RuntimeError(f'{label} sayfa {page} tamamlanamadı: {e}') from e

        if not rows:
            return out, ''
        if any(_wrong_kind(r) for r in rows if isinstance(r, dict)):
            return [], f'{label}: filtre yok sayıldı; başka fatura türleri döndü.'

        new_count = 0
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            rec = audit._doc_record(raw, 'GENERAL EXPENSE', 'INVOICES/V1')
            key = rec['document_id'] or '|'.join((
                rec['serial_no'], rec['document_no'], rec['invoice_number'],
                str(rec['amount']), rec['issue_date']
            ))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(rec)
            new_count += 1

        if len(rows) < PAGE_SIZE:
            return out, ''
        if new_count == 0:
            raise RuntimeError(f'{label}: aynı sayfa tekrarlandı; eksik liste kabul edilmedi.')
        if page >= MAX_PAGES:
            raise RuntimeError(f'{label}: {MAX_PAGES * PAGE_SIZE} belge sınırına ulaştı; eksik liste kabul edilmedi.')
        time.sleep(PAGE_DELAY)
    return out, ''


def _fetch_general_expenses_v1_only():
    errors = []
    for params, label in (
        ({'type': 'general_expense'}, 'v1 type=general_expense'),
        ({'commercial_doc_type': 'general_expense'}, 'v1 commercial_doc_type=general_expense'),
    ):
        rows, err = _scan(params, label)
        if rows:
            return rows, errors
        if err:
            errors.append(err)
        time.sleep(PAGE_DELAY)
    raise RuntimeError(
        'GENERAL EXPENSE resmi /invoices listesinden alınamadı. Ayrı bir Office token kullanılmayacak. ' +
        (' | '.join(errors[-2:]) if errors else 'General Expense listesi boş döndü.')
    )


audit._fetch_general_expenses = _fetch_general_expenses_v1_only

# Remove the temporary Office-token card. No script blocks are added or changed.
start = html.find('<div class="calc" id="kbOfficeTokenCard"')
marker = '<textarea id="kbAuditInput"'
if start >= 0:
    end = html.find(marker, start)
    if end > start:
        html = html[:start] + html[end:]

core.HTML = html
print('[SAMA] GENERAL EXPENSE audit uses official /invoices list only; temporary Office-token UI removed')
