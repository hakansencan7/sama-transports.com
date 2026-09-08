from pathlib import Path

p = Path('app.py')
s = p.read_text(encoding='utf-8')
MARK = '// SAMA_I18N_SELECTOR_MAIN_PAGE_V3'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

needle = "  window.setSamaLanguage=applyLanguage;\n  document.querySelectorAll('#samaLangBox button').forEach(b=>b.addEventListener('click',()=>applyLanguage(b.dataset.lang)));"
replacement = "  // SAMA_I18N_SELECTOR_MAIN_PAGE_V3\n  // The selector was rendered inside authOverlay, so hiding the login overlay also hid the selector.\n  // Move only the selector to body; it then stays visible on the authenticated main UI.\n  const samaLangBox=document.getElementById('samaLangBox');\n  if(samaLangBox && samaLangBox.parentElement!==document.body){document.body.appendChild(samaLangBox);}\n  window.setSamaLanguage=applyLanguage;\n  document.querySelectorAll('#samaLangBox button').forEach(b=>b.addEventListener('click',()=>applyLanguage(b.dataset.lang)));"

if needle not in s:
    raise SystemExit('i18n selector hook not found')

s = s.replace(needle, replacement, 1)
p.write_text(s, encoding='utf-8')
print('patched')
