# Final browser-scope fix for Entry OTHER and completed Entry editing.
# app.py declares the active trip as a top-level lexical `let cx`, so it is NOT available as window.cx.
# Older Entry OTHER helpers used window.cx and therefore could show values in the form without ever
# persisting them to SQLite. Print then correctly read zero/blank values from the database.

import shipment_edit_money_patch as base

app = base.app
core = base.core
html = core.HTML

replacements = {
    "String((window.cx&&cx.scna)||'').trim()": "String(((typeof cx!=='undefined'&&cx&&cx.scna)?cx.scna:'')||'').trim()",
    "if(!window.cx)return;": "try{if(typeof cx==='undefined'||!cx)return;}catch(_e){return;}",
    "Number(window.cx?.entry_done||0)": "Number(((typeof cx!=='undefined'&&cx)?cx.entry_done:0)||0)",
}

counts = {}
for old, new in replacements.items():
    n = html.count(old)
    counts[old] = n
    if n:
        html = html.replace(old, new)

core.HTML = html
print('[SAMA] Entry OTHER lexical cx scope fix active:', {k: v for k, v in counts.items() if v})
