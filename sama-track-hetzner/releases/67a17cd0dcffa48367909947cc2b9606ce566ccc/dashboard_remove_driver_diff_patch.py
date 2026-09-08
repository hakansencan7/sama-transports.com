import driver_status_main_sync_patch as base

app = base.app
core = base.core
html = core.HTML

# Remove only the main dashboard's driver account difference card/column.
# Entry settlement and reporting calculations stay intact.
html = html.replace('<div class="card">Şoför Hesap Farkı<b id="dDiff">0</b></div>', '', 1)
html = html.replace('<th>ŞOFÖR HESAP FARKI</th>\n', '', 1)

old_js = '''  dDue.innerText=money(s.due_total||0);\n  dDiff.innerText=money(s.driver_diff||0);\n\n  let totalDiff=Number(s.driver_diff||0);\n  let diffCard=dDiff.closest('.card');\n  diffCard.classList.remove('diff-red','diff-green');\n  if(totalDiff<0) diffCard.classList.add('diff-red');\n  else if(totalDiff>0) diffCard.classList.add('diff-green');\n'''
new_js = '''  dDue.innerText=money(s.due_total||0);\n'''
html = html.replace(old_js, new_js, 1)

old_row = '''      <td>${money(x.freight_total)}</td><td>${money(x.expected_cash_handover)}</td>\n      <td style="font-weight:800">${money(x.amount_due)}</td><td ${diffClass}>${money(x.driver_cash_diff)}</td>\n      <td>${sBadge(x.driver_cash_status)}</td></tr>`;'''
new_row = '''      <td>${money(x.freight_total)}</td><td>${money(x.expected_cash_handover)}</td>\n      <td style="font-weight:800">${money(x.amount_due)}</td>\n      <td>${sBadge(x.driver_cash_status)}</td></tr>`;'''
html = html.replace(old_row, new_row, 1)

# Remove the now-unused per-row color helper from the dashboard render only.
html = html.replace("    let diffClass=Number(x.driver_cash_diff||0)<0?'style=\"background:#fee2e2;color:#991b1b;font-weight:800\"':\n                  Number(x.driver_cash_diff||0)>0?'style=\"background:#dcfce7;color:#166534;font-weight:800\"':'';\n", '', 1)

core.HTML = html
print('[SAMA] Main dashboard driver account difference removed')
