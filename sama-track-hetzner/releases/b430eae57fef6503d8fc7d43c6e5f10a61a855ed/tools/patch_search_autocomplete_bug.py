from pathlib import Path

p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='// SAMA_SEARCH_AUTOCOMPLETE_FIX_V1'
if MARK in s:
    print('already patched')
    raise SystemExit(0)

old="""    const isSearch=ph.includes('ara')||id.endsWith('q')||id.includes('filter');
    if(id.includes('plate')||ph.includes('plaka')||label.includes('plaka')) samaAttachAutocomplete(el,'plate');
    else if(!isSearch&&(id.includes('driver')||ph.includes('şoför')||ph.includes('sofor')||label.includes('şoför')||label.includes('sofor'))) samaAttachAutocomplete(el,'driver');"""
new="""    const isSearch=ph.includes('ara')||id.endsWith('q')||id.includes('filter');
    // SAMA_SEARCH_AUTOCOMPLETE_FIX_V1
    if(!isSearch&&(id.includes('plate')||ph.includes('plaka')||label.includes('plaka'))) samaAttachAutocomplete(el,'plate');
    else if(!isSearch&&(id.includes('driver')||ph.includes('şoför')||ph.includes('sofor')||label.includes('şoför')||label.includes('sofor'))) samaAttachAutocomplete(el,'driver');"""
if old not in s:
    raise RuntimeError('autocomplete init anchor not found')
s=s.replace(old,new,1)

# Explicitly mark Avans search as not eligible for field autocomplete too.
s=s.replace('id="advQ" class="grow" placeholder="Kişi / plaka / iş / SCNA ara"',
            'id="advQ" class="grow" data-no-autocomplete="1" autocomplete="off" placeholder="Kişi / plaka / iş / SCNA ara"',1)

p.write_text(s,encoding='utf-8')
print('patched search autocomplete bug')
