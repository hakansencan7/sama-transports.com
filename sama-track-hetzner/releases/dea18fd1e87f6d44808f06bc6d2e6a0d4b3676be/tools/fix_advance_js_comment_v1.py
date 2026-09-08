from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
old='# SAMA_ADVANCE_AUTOCOMPLETE_V2'
new='// SAMA_ADVANCE_AUTOCOMPLETE_V2'
if old not in s:
    raise SystemExit('marker not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('fixed invalid JS comment')
