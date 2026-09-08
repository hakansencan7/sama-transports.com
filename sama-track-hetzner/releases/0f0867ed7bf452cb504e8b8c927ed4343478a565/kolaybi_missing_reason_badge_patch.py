import kolaybi_invoice_metadata_serial_patch as base

app = base.app
core = base.core
html = core.HTML

# The transaction cards already calculate exact missing_reasons server-side.
# Surface them directly in the header badge so "EKSİK" is never a mystery diagnosis.
old_purchase = "if(ps)ps.innerHTML=sent.purchase?'<span class=\"kb-ready\">✓ GÖNDERİLDİ</span>':(p.ready?'<span class=\"kb-ready\">✓ HAZIR</span>':'<span class=\"kb-missing\">EKSİK</span>');"
new_purchase = "if(ps)ps.innerHTML=sent.purchase?'<span class=\"kb-ready\">✓ GÖNDERİLDİ</span>':(p.ready?'<span class=\"kb-ready\">✓ HAZIR</span>':'<span class=\"kb-missing\" title=\"'+kbEsc((p.missing_reasons||[]).join(' | '))+'\">EKSİK: '+kbEsc((p.missing_reasons||[]).join(' | ')||'NEDEN BELİRLENEMEDİ')+'</span>');"

old_sale = "if(ss)ss.innerHTML=sent.sale?'<span class=\"kb-ready\">✓ GÖNDERİLDİ</span>':(s.ready?'<span class=\"kb-ready\">✓ HAZIR</span>':'<span class=\"kb-missing\">EKSİK</span>');"
new_sale = "if(ss)ss.innerHTML=sent.sale?'<span class=\"kb-ready\">✓ GÖNDERİLDİ</span>':(s.ready?'<span class=\"kb-ready\">✓ HAZIR</span>':'<span class=\"kb-missing\" title=\"'+kbEsc((s.missing_reasons||[]).join(' | '))+'\">EKSİK: '+kbEsc((s.missing_reasons||[]).join(' | ')||'NEDEN BELİRLENEMEDİ')+'</span>');"

if old_purchase in html:
    html = html.replace(old_purchase, new_purchase, 1)
if old_sale in html:
    html = html.replace(old_sale, new_sale, 1)

# Also make the existing missing-reason box visually explicit.
html = html.replace(
    "<div class=\"kb-missing\" style=\"margin:8px 0\">${kbEsc(p.missing_reasons.join(' | '))}</div>",
    "<div class=\"kb-missing\" style=\"margin:8px 0;font-weight:700\">EKSİK OLAN: ${kbEsc(p.missing_reasons.join(' | '))}</div>",
    1,
)
html = html.replace(
    "<div class=\"kb-missing\" style=\"margin:8px 0\">${kbEsc(s.missing_reasons.join(' | '))}</div>",
    "<div class=\"kb-missing\" style=\"margin:8px 0;font-weight:700\">EKSİK OLAN: ${kbEsc(s.missing_reasons.join(' | '))}</div>",
    1,
)

core.HTML = html
print('[SAMA] KolayBi missing-reason badges active: PURCHASE/SALE show exact blocking fields')
