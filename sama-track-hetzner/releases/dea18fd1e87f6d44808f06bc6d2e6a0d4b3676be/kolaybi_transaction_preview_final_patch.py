import re
import kolaybi_legacy_invoice_items_patch as legacy

app = legacy.app
core = legacy.core
v3 = legacy.v3
workflow = v3.base


def _txt(v):
    return str(v or '').strip()


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _fmt(v):
    s = f'{_num(v):.6f}'.rstrip('0').rstrip('.')
    return s or '0'


def _sale_preview_final(scna, trip=None, purchase=None):
    trip = trip or workflow._trip(scna)
    purchase = purchase or workflow._purchase_preview(scna,trip)
    customer = _txt(trip.get('customer_name'))
    contact, source, candidates = v3._resolve_sale(customer)
    area = _txt(trip.get('area_name'))
    product = workflow._sale_product(area)
    basis = _txt(trip.get('freight_basis') or 'KG').upper()
    qty = _num(trip.get('net_kg')) if basis == 'KG' else 1.0
    rate = _num(trip.get('freight_rate'))
    imported = _num(trip.get('excel_amount'))
    if imported > 0:
        total = imported
        unit_price = total/qty if qty > 0 else total
        amount_source = 'IMPORTED AMOUNT'
    elif basis == 'KG':
        total = qty * rate
        unit_price = rate
        amount_source = 'NET KG × FREIGHT RATE'
    else:
        qty = 1.0
        total = rate
        unit_price = rate
        amount_source = 'ADET × FREIGHT RATE'

    pid = _txt((product or {}).get('product_id'))
    pname = _txt((product or {}).get('product_name') or (product or {}).get('name_tr') or (product or {}).get('name_en') or area)
    unit = 'KG' if basis == 'KG' else 'ADET'
    project = purchase.get('project') or {}
    missing=[]
    if not contact:
        missing.append('SALE CARİ: '+(customer or '-'))
    elif not _txt(contact.get('contact_id')):
        missing.append('SALE CONTACT ID')
    if contact and not _txt(contact.get('address_id')):
        missing.append('SALE ADDRESS ID')
    if not pid:
        missing.append('SALE ÜRÜN ALIAS/PRODUCT ID: '+(area or 'NAKLİYE HİZMETİ'))
    if not _txt(project.get('project_id')):
        missing.append('PROJECT ID')
    if qty <= 0:
        missing.append('SALE QUANTITY')
    if total <= 0:
        missing.append('SALE AMOUNT')

    parts = ['SNCA'+re.sub(r'^(SNCA|SCNA)','',_txt(scna).upper())]
    if _txt(trip.get('driver_name')):
        parts.append('DRIVER: '+_txt(trip.get('driver_name')))
    if _txt(trip.get('plate')):
        parts.append('PLATE: '+_txt(trip.get('plate')))
    if _num(trip.get('net_kg')) > 0:
        parts.append('WEIGHT: '+_fmt(trip.get('net_kg'))+' KG')

    return {
        'scna':_txt(scna),'plate':_txt(trip.get('plate')),'driver':_txt(trip.get('driver_name')),
        'customer':customer,'contact':contact,'contact_source':source,
        'contact_candidates':[{'name':v3._display(x),'contact_id':_txt(x.get('contact_id')),'address_id':_txt(x.get('address_id'))} for x in candidates[:6]],
        'project':project,'area_name':area,'product':product,'product_id':pid,'product_name':pname,
        'product_match_source':_txt((product or {}).get('match_source')),'basis':basis,'quantity':qty,
        'unit_price':unit_price,'total':total,'unit':unit,'amount_source':amount_source,
        'collection':_num(trip.get('entry_collection')),'description':'\n'.join(parts),
        'missing_reasons':missing,'ready':not missing,
    }


workflow._sale_preview = _sale_preview_final
v3._sale_preview_v3 = _sale_preview_final

print('[SAMA] KolayBi final transaction preview active: single-pass SALE contact resolution + authoritative KG/ADET unit')
