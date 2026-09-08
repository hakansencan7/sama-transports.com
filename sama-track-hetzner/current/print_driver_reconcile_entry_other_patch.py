# Final print cash-reconciliation fix.
# The print rows are now the authoritative source for RETURN EXPENSES because they already
# include ROAD FUEL + WEIGHBRIDGE + PARKING + WAITING + dedicated ENTRY OTHER rows.
# This prevents a valid ENTRY OTHER (for example 15,000 IQD TAXI) from appearing as a
# false DRIVER DIFFERENCE simply because the old summary formula only summed entry_extra_1..3.
# No separate <script> block is added; this safely patches the existing print JS only.

import entry_fixed_other_kolaybi_final_patch as base

app = base.app
core = base.core
html = core.HTML

# After print expense rows are classified, recompute the driver settlement from the exact
# return rows that are actually printed. This automatically covers future Entry OTHER rows too.
old_rows_calc = "const allExpenseTotal=exitExpenseTotal+returnExpenseTotal;visibleRows.forEach((r,i)=>r[0]=String(i+1));\n  const doc=`"
new_rows_calc = "const allExpenseTotal=exitExpenseTotal+returnExpenseTotal;const driverMustReturnPrint=collectionRecorded?Math.max(customerPaid-returnExpenseTotal,0):Math.max(freight-returnExpenseTotal,0);const driverCashDiffPrint=collectionRecorded?(driverCashHanded-driverMustReturnPrint):0;visibleRows.forEach((r,i)=>r[0]=String(i+1));\n  const doc=`"
rows_calc_patched = 0
if old_rows_calc in html:
    html = html.replace(old_rows_calc, new_rows_calc, 1)
    rows_calc_patched = 1

# Change only the visible reconciliation boxes. The original variables remain untouched for
# older/other code paths, while the print uses the authoritative itemized return total.
old_box = '''<div class="cashReconcile"><div class="crb"><div class="crt">WE SHOULD RECEIVE FROM DRIVER</div><div class="crar">المبلغ الواجب استلامه من السائق</div><div class="crv">${fmt(driverMustReturn)}</div></div><div class="crb"><div class="crt">RECEIVED FROM DRIVER</div><div class="crar">المبلغ المستلم من السائق</div><div class="crv">${fmt(driverCashHanded)}</div></div><div class="crb ${driverCashDiff<0?'short':''}"><div class="crt">DRIVER DIFFERENCE</div><div class="crar">فرق حساب السائق</div><div class="crv">${fmt(driverCashDiff)}</div></div></div>'''
new_box = '''<div class="cashReconcile"><div class="crb"><div class="crt">WE SHOULD RECEIVE FROM DRIVER</div><div class="crar">المبلغ الواجب استلامه من السائق</div><div class="crv">${fmt(driverMustReturnPrint)}</div></div><div class="crb"><div class="crt">RECEIVED FROM DRIVER</div><div class="crar">المبلغ المستلم من السائق</div><div class="crv">${fmt(driverCashHanded)}</div></div><div class="crb ${driverCashDiffPrint<0?'short':''}"><div class="crt">DRIVER DIFFERENCE</div><div class="crar">فرق حساب السائق</div><div class="crv">${fmt(driverCashDiffPrint)}</div></div></div>'''
box_patched = 0
if old_box in html:
    html = html.replace(old_box, new_box, 1)
    box_patched = 1

core.HTML = html
print(f'[SAMA] Print driver reconciliation uses itemized return expenses: rows_calc={rows_calc_patched}, box={box_patched}')
