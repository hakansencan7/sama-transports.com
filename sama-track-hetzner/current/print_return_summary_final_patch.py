# Final print reconciliation for return expenses.
# The itemized print rows are authoritative: RETURN total must include every
# printed return expense (fixed expenses, dedicated OTHER rows and road fuel).
# This patch only changes the print renderer. It does not mutate shipment data.

import print_return_total_label_patch as base

core = base.core
app = base.app
html = core.HTML

# Once the renderer has classified the itemized rows, calculate the driver
# settlement from the exact RETURN total shown in the table.
calc_anchor = "const allExpenseTotal=exitExpenseTotal+returnExpenseTotal;"
if "const driverMustReturnPrint=" not in html and calc_anchor in html:
    html = html.replace(
        calc_anchor,
        calc_anchor
        + "const driverMustReturnPrint=collectionRecorded?Math.max(customerPaid-returnExpenseTotal,0):Math.max(freight-returnExpenseTotal,0);"
        + "const driverCashDiffPrint=collectionRecorded?(driverCashHanded-driverMustReturnPrint):0;",
        1,
    )

# Lower summary: do not show the legacy entry_extra_1..3 subtotal. Show the
# same authoritative RETURN total that is printed in the itemized table.
html = html.replace(
    '<span>RETURN EXTRA EXPENSES</span><span>مصاريف العودة الإضافية</span>',
    '<span>TOTAL RETURN EXPENSES</span><span>مجموع مصاريف العودة</span>',
)
html = html.replace(
    '${entryExtras?`<div class="srow">',
    '${returnExpenseTotal?`<div class="srow">',
)
html = html.replace(
    '<div class="sval">${fmt(entryExtras)}</div></div>',
    '<div class="sval">${fmt(returnExpenseTotal)}</div></div>',
)

# Every visible DRIVER SHOULD HAND OVER / reconciliation value must use the
# itemized return total too, so OTHER 1/2 can never disappear from settlement.
if "const driverMustReturnPrint=" in html:
    html = html.replace('${fmt(driverMustReturn)}', '${fmt(driverMustReturnPrint)}')
    html = html.replace("${driverCashDiff<0?'short':''}", "${driverCashDiffPrint<0?'short':''}")
    html = html.replace('${fmt(driverCashDiff)}', '${fmt(driverCashDiffPrint)}')

# Idempotent labels for both print render paths.
html = html.replace(
    '<b>RETURN EXTRA EXPENSES</b><span class="rtlRight">مصاريف العودة الإضافية</span>',
    '<b>RETURN EXPENSES (FUEL + EXTRA)</b><span class="rtlRight">مصاريف العودة (الوقود + الإضافية)</span>',
)
html = html.replace(
    '<b>TOTAL RETURN EXTRA EXPENSES</b><span class="rtlRight">مجموع مصاريف العودة الإضافية</span>',
    '<b>TOTAL RETURN EXPENSES</b><span class="rtlRight">مجموع مصاريف العودة</span>',
)

core.HTML = html
print('[SAMA] Final print return summary uses itemized returnExpenseTotal for summary and driver settlement')
