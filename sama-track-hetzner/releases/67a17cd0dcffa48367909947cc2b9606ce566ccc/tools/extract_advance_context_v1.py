from pathlib import Path
s=Path('app.py').read_text(encoding='utf-8')
needles=['advance_settlement','advance_settlements','/api/advances','Hesaplaşmalar','Fatura / Fiş / İade','settlement']
out=[]
for needle in needles:
    start=0
    while True:
        i=s.lower().find(needle.lower(),start)
        if i<0: break
        a=max(0,i-1800); b=min(len(s),i+4200)
        out.append(f'\n===== {needle} @ {i} =====\n'+s[a:b])
        start=i+len(needle)
Path('tools/advance_context_v1.txt').write_text('\n'.join(out),encoding='utf-8')
print('matches',len(out))
