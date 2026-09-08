import layout_patch as layout

core = layout.patched.core
app = layout.app
html = core.HTML

html = html.replace('SHIPMENT No. (SNCA)', 'SHIPMENT No. (SCNA)')

# Cash reconciliation. Customer shortage is customer debt, not driver shortage.
html = html.replace(
    "const entryExtras=entryExtra1+entryExtra2+entryExtra3,returnExpenses=roadFuel+entryExtras,driverMustReturn=freight-returnExpenses,routeKm=n(x.planned_km_go);",
    "const entryExtras=entryExtra1+entryExtra2+entryExtra3,returnExpenses=roadFuel+entryExtras,customerPaid=n(x.entry_collection),driverCashHanded=n(x.entry_cash_handed),collectionRecorded=Boolean(n(x.entry_done))||customerPaid>0||driverCashHanded>0,customerRemaining=collectionRecorded?Math.max(freight-customerPaid,0):0,driverMustReturn=collectionRecorded?Math.max(customerPaid-returnExpenses,0):Math.max(freight-returnExpenses,0),driverCashDiff=collectionRecorded?(driverCashHanded-driverMustReturn):0,routeKm=n(x.planned_km_go);"
)

# Append return expenses, hide every zero-amount line, then split exit/return totals.
html = html.replace(
    "if(pe&&Array.isArray(pe.rows)){pe.rows.forEach(r=>rows.push(r));}\n  const doc=`",
    "if(pe&&Array.isArray(pe.rows)){pe.rows.forEach(r=>rows.push(r));}const visibleRows=rows.filter(r=>Math.abs(n(r[4]))>0.000001);const exitRows=visibleRows.filter(r=>!String(r[5]||'').includes('entryExpense'));const returnRows=visibleRows.filter(r=>String(r[5]||'').includes('entryExpense'));const exitExpenseTotal=exitRows.reduce((s,r)=>s+n(r[4]),0);const returnExpenseTotal=returnRows.reduce((s,r)=>s+n(r[4]),0);const allExpenseTotal=exitExpenseTotal+returnExpenseTotal;visibleRows.forEach((r,i)=>r[0]=String(i+1));\n  const doc=`"
)

old_rows = "${rows.map(r=>`<tr class=\"${r[5]||''}\"><td class=\"no\">${r[0]}</td><td class=\"detail\"><span class=\"en\">${r[1]}</span><span class=\"ar\">${r[2]}</span>${r[6]?`<span class=\"entryReason\">${esc(r[6])}</span>`:''}</td><td class=\"price\">${r[3]}</td><td class=\"amt\">${fmt(r[4])}</td></tr>`).join('')}<tr class=\"total\"><td colspan=\"2\" class=\"label\">TOTAL EXPENSES &nbsp;&nbsp; مجموع المصاريف</td><td></td><td class=\"amt\">${fmt(totalExpenses)}</td></tr>"
new_rows = "${exitRows.map(r=>`<tr><td class=\"no\">${r[0]}</td><td class=\"detail\"><span class=\"en\">${r[1]}</span><span class=\"ar\">${r[2]}</span>${r[6]?`<span class=\"entryReason\">${esc(r[6])}</span>`:''}</td><td class=\"price\">${r[3]}</td><td class=\"amt\">${fmt(r[4])}</td></tr>`).join('')}<tr class=\"expenseSubtotal\"><td colspan=\"3\"><b>EXIT EXPENSES TOTAL</b><span class=\"rtlRight\">مجموع مصاريف الخروج</span></td><td class=\"amt\"><b>${fmt(exitExpenseTotal)}</b></td></tr>${returnRows.length?`<tr class=\"returnHeader\"><td colspan=\"4\"><b>RETURN EXTRA EXPENSES</b><span class=\"rtlRight\">مصاريف العودة الإضافية</span></td></tr>${returnRows.map(r=>`<tr class=\"entryExpense\"><td class=\"no\">${r[0]}</td><td class=\"detail\"><span class=\"en\">${r[1]}</span><span class=\"ar\">${r[2]}</span>${r[6]?`<span class=\"entryReason\">${esc(r[6])}</span>`:''}</td><td class=\"price\">${r[3]}</td><td class=\"amt\">${fmt(r[4])}</td></tr>`).join('')}<tr class=\"returnSubtotal\"><td colspan=\"3\"><b>TOTAL RETURN EXTRA EXPENSES</b><span class=\"rtlRight\">مجموع مصاريف العودة الإضافية</span></td><td class=\"amt\"><b>${fmt(returnExpenseTotal)}</b></td></tr>`:''}<tr class=\"grandExpenseTotal\"><td colspan=\"3\"><b>TOTAL EXPENSES (EXIT + RETURN)</b><span class=\"rtlRight\">إجمالي المصاريف</span></td><td class=\"amt\"><b>${fmt(allExpenseTotal)}</b></td></tr>"
html = html.replace(old_rows, new_rows)

# Fallback renderer for the unclassified base version.
old_base = "${rows.map(r=>`<tr><td class=\"no\">${r[0]}</td><td class=\"detail\"><span class=\"en\">${r[1]}</span><span class=\"ar\">${r[2]}</span></td><td class=\"price\">${r[3]}</td><td class=\"amt\">${fmt(r[4])}</td></tr>`).join('')}<tr class=\"total\"><td colspan=\"2\" class=\"label\">TOTAL EXPENSES &nbsp;&nbsp; مجموع المصاريف</td><td></td><td class=\"amt\">${fmt(totalExpenses)}</td></tr>"
html = html.replace(old_base, new_rows)

# Styles for split expense totals and reconciliation boxes.
html = html.replace(
    '.entryReason{display:block;clear:both;font-size:7.8px;font-weight:700;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.entryReason{display:block;clear:both;font-size:7.8px;font-weight:700;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rtlRight{float:right;direction:rtl}.expenseSubtotal td{border-top:2px solid #111!important;font-weight:900}.returnHeader td{border:2px solid #111!important;color:#b00020;font-weight:900}.entryExpense td{color:#b00020!important;font-weight:900}.returnSubtotal td{border:2px solid #111!important;color:#b00020;font-weight:900}.grandExpenseTotal td{border:2.5px solid #111!important;font-size:11px;font-weight:900}.customerSettle{display:grid;grid-template-columns:1fr 1fr;border:2px solid #111;margin-top:1mm}.customerSettle .csb{text-align:center;padding:1.2mm;border-right:2px solid #111}.customerSettle .csb:last-child{border-right:0}.customerSettle .cst{font-size:9px;font-weight:900}.customerSettle .csar{direction:rtl;font-size:8.5px;font-weight:800}.customerSettle .csv{font-size:20px;font-weight:900;margin-top:1mm}.customerSettle .due{color:#b00020}.cashReconcile{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:2px solid #111;margin-top:1mm}.cashReconcile .crb{text-align:center;padding:1.2mm;border-right:2px solid #111}.cashReconcile .crb:last-child{border-right:0}.cashReconcile .crt{font-size:8.5px;font-weight:900}.cashReconcile .crar{direction:rtl;font-size:8px;font-weight:800}.cashReconcile .crv{font-size:19px;font-weight:900;margin-top:1mm}.cashReconcile .short{color:#b00020}'
)

# Hide zero-valued optional summary lines too.
html = html.replace('<div class="srow"><div class="slab"><span>OTHER EXPENSE</span><span>مصاريف أخرى</span></div><div></div><div class="sval">${fmt(other)}</div></div>','${other?`<div class="srow"><div class="slab"><span>OTHER EXPENSE</span><span>مصاريف أخرى</span></div><div></div><div class="sval">${fmt(other)}</div></div>`:``}')
html = html.replace('<div class="srow"><div class="slab"><span>ROAD FUEL EXPENSE</span><span>مصاريف وقود الطريق</span></div><div></div><div class="sval">${fmt(roadFuel)}</div></div>','${roadFuel?`<div class="srow"><div class="slab"><span>ROAD FUEL EXPENSE</span><span>مصاريف وقود الطريق</span></div><div></div><div class="sval">${fmt(roadFuel)}</div></div>`:``}')
html = html.replace('<div class="srow"><div class="slab"><span>RETURN EXTRA EXPENSES</span><span>مصاريف العودة الإضافية</span></div><div></div><div class="sval">${fmt(entryExtras)}</div></div>','${entryExtras?`<div class="srow"><div class="slab"><span>RETURN EXTRA EXPENSES</span><span>مصاريف العودة الإضافية</span></div><div></div><div class="sval">${fmt(entryExtras)}</div></div>`:``}')

old_money = '''<div class="money"><div class="mb"><div class="mt">TOTAL FREIGHT</div><div class="mar">مجموع النقل</div><div class="mv">${fmt(freight)}</div></div><div class="mb"><div class="mt">RETURN EXPENSES</div><div class="mar">مصاريف العودة</div><div class="mv">${fmt(returnExpenses)}</div></div><div class="mb"><div class="mt">DRIVER MUST RETURN</div><div class="mar">المبلغ الذي يجب على السائق تسليمه</div><div class="mv">${fmt(driverMustReturn)}</div></div></div>'''
new_money = '''<div class="customerSettle"><div class="csb"><div class="cst">CUSTOMER PAID</div><div class="csar">المبلغ المدفوع من العميل</div><div class="csv">${fmt(customerPaid)}</div></div><div class="csb due"><div class="cst">AMOUNT TO RECEIVE FROM CUSTOMER</div><div class="csar">المبلغ المتبقي على العميل</div><div class="csv">${fmt(customerRemaining)}</div></div></div><div class="cashReconcile"><div class="crb"><div class="crt">WE SHOULD RECEIVE FROM DRIVER</div><div class="crar">المبلغ الواجب استلامه من السائق</div><div class="crv">${fmt(driverMustReturn)}</div></div><div class="crb"><div class="crt">RECEIVED FROM DRIVER</div><div class="crar">المبلغ المستلم من السائق</div><div class="crv">${fmt(driverCashHanded)}</div></div><div class="crb ${driverCashDiff<0?'short':''}"><div class="crt">DRIVER DIFFERENCE</div><div class="crar">فرق حساب السائق</div><div class="crv">${fmt(driverCashDiff)}</div></div></div>'''
html = html.replace(old_money, new_money)
html = html.replace('<span>DRIVER MUST RETURN</span><span>المبلغ الذي يجب على السائق تسليمه</span>','<span>DRIVER SHOULD HAND OVER</span><span>المبلغ الذي يجب على السائق تسليمه</span>')

core.HTML = html


def _audited_print_entry_expenses(scna: str):
    key = str(scna or '').strip()
    c = core.db()
    try:
        trip = c.execute('SELECT entry_extra_expense_1,entry_extra_expense_2,entry_extra_expense_3,entry_note FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))',(key,)).fetchone()
        fuels = c.execute('SELECT liters,total,note FROM fuel_purchases WHERE UPPER(TRIM(scna))=UPPER(TRIM(?)) ORDER BY id',(key,)).fetchall()
        try:
            labels = {int(r['slot']): str(r['label'] or '').strip() for r in c.execute('SELECT slot,label FROM trip_entry_expense_labels WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))',(key,)).fetchall()}
        except Exception:
            labels = {}
        rows = []
        road_total = sum(float(r['total'] or 0) for r in fuels)
        road_liters = sum(float(r['liters'] or 0) for r in fuels)
        fuel_notes = [str(r['note'] or '').strip() for r in fuels if str(r['note'] or '').strip()]
        if road_total:
            rows.append(['','Road Fuel Expense (RETURN)','مصاريف وقود طريق العودة',f'{road_liters:g} L' if road_liters else '-',road_total,'entryExpense','; '.join(dict.fromkeys(fuel_notes))])
        if trip:
            note = str(trip['entry_note'] or '').strip()
            extras = [float(trip['entry_extra_expense_1'] or 0),float(trip['entry_extra_expense_2'] or 0),float(trip['entry_extra_expense_3'] or 0)]
            for idx, amount in enumerate(extras, 1):
                if amount:
                    rows.append(['',labels.get(idx) or f'Return Extra Expense {idx}',f'مصاريف عودة إضافية {idx}','-',amount,'entryExpense',note])
        return {'ok': True, 'rows': rows}
    finally:
        c.close()

for route in app.routes:
    if getattr(route,'path',None) == '/api/print-entry-expenses/{scna}' and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint = _audited_print_entry_expenses
        if getattr(route,'dependant',None) is not None:
            route.dependant.call = _audited_print_entry_expenses
        break
