import print_audit_patch as base

core = base.core
app = base.app

# The print renderer's return subtotal includes BOTH return road fuel and
# return extra expenses. The old caption incorrectly called that combined
# amount "TOTAL RETURN EXTRA EXPENSES", which made a valid 10,000 fuel +
# 15,000 extra = 25,000 total look like an arithmetic error.
html = core.HTML
html = html.replace(
    '<b>RETURN EXTRA EXPENSES</b><span class="rtlRight">مصاريف العودة الإضافية</span>',
    '<b>RETURN EXPENSES (FUEL + EXTRA)</b><span class="rtlRight">مصاريف العودة (الوقود + الإضافية)</span>',
)
html = html.replace(
    '<b>TOTAL RETURN EXTRA EXPENSES</b><span class="rtlRight">مجموع مصاريف العودة الإضافية</span>',
    '<b>TOTAL RETURN EXPENSES</b><span class="rtlRight">مجموع مصاريف العودة</span>',
)
core.HTML = html
