from pathlib import Path
import re

p=Path('app.py')
s=p.read_text(encoding='utf-8')
if '// SAMA_I18N_COMPREHENSIVE_V5' in s:
    print('v5 already applied')
    raise SystemExit(0)
pat=r"  function translateString\(raw,l\)\{.*?\n  \}\n  function translateNode"
repl="""  function translateString(value,l){
    const raw=value==null?'':String(value), key=raw.trim();
    if(l==='tr'||!key)return raw;
    const translated=DICT[l]&&DICT[l][key];
    return translated?raw.replace(key,translated):raw;
  }
  function translateNode"""
s2,n=re.subn(pat,repl,s,count=1,flags=re.S)
if n==0:
    print('translator already normalized or pattern not found')
else:
    p.write_text(s2,encoding='utf-8')
    print('translator normalized')
