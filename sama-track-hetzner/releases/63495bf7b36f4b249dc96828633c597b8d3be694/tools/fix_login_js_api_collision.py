from pathlib import Path
import re

p=Path('app.py')
s=p.read_text(encoding='utf-8')
ms=list(re.finditer(r'<script[^>]*>(.*?)</script>',s,flags=re.S|re.I))
if len(ms)<2:
    raise SystemExit('Expected at least 2 script blocks')
m=ms[0]
block=m.group(1)
orig=block
block=re.sub(r'\bfunction\s+api\s*\(', 'function authApi(', block)
block=re.sub(r'\b(const|let|var)\s+api\s*=', lambda x:f"{x.group(1)} authApi=", block)
block=re.sub(r'\bapi\s*\(', 'authApi(', block)
if block==orig:
    raise SystemExit('No api identifier found in first script block')
s=s[:m.start(1)]+block+s[m.end(1):]
if 'SAMA_LOGIN_JS_API_COLLISION_FIX_V1' not in s:
    s=s.replace(block, '/* SAMA_LOGIN_JS_API_COLLISION_FIX_V1 */\n'+block,1)
p.write_text(s,encoding='utf-8')
print('First script api identifier renamed to authApi; login collision fix ready')
