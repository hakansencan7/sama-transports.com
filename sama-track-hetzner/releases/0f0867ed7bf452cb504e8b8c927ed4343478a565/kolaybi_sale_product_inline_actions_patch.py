# Final UI guarantee for missing SALE products.
# Keeps the existing login/HTML structure intact and only injects controls inside the existing JS template.
import kolaybi_sale_product_workflow_patch as base

app = base.app
core = base.core
html = core.HTML

needle = '${sMissing}<div class="table">'
replacement = '''${!s.product_id?`<div id="kbSaleProductInlineActions" class="kb-sale-product-alert" style="margin:9px 0">
  <b>SATIŞ ÜRÜNÜ BULUNAMADI / EŞLEŞMEDİ</b><br>
  <span>Bölge / ürün: <strong>${kbEsc(s.area_name||'-')}</strong></span><br>
  <small>Önce KolayBi'de mevcut ürünü ara ve bu bölgeye eşleştir. Gerçekten yoksa yeni ürün oluştur.</small>
  <div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:8px">
    <button class="btn secondary" onclick="kbSaleProductOpen('${kbEsc(scna)}')">ÜRÜN ARA / EŞLEŞTİR</button>
    <button class="btn primary" onclick="kbSaleProductOpen('${kbEsc(scna)}',true)">YENİ ÜRÜN OLUŞTUR</button>
  </div>
</div>`:''}${sMissing}<div class="table">'''

inserted = 0
if needle in html and 'id="kbSaleProductInlineActions"' not in html:
    html = html.replace(needle, replacement, 1)
    inserted = 1

core.HTML = html
print(f'[SAMA] SALE missing-product inline actions active: inserted={inserted}')
