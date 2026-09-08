import print_audit_patch as print_patch

app = print_patch.app
core = print_patch.core

html = core.HTML

old = """      closeM();
      loadEntry();"""
new = """      closeM();
      loadEntry();
      if(confirm('Giriş kaydı tamamlandı. Şimdi yazdırmak ister misiniz?')){
        printTrip(scna,'GİRİŞ');
      }"""

if old not in html:
    raise RuntimeError('entry save success anchor not found')

html = html.replace(old, new, 1)
core.HTML = html
print('[SAMA] Entry save -> direct print prompt active')
