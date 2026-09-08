from pathlib import Path
p=Path('app.py')
s=p.read_text(encoding='utf-8')
MARK='<!-- SAMA_FINANCE_NAV_V1 -->'
if MARK in s:
    print('already patched'); raise SystemExit(0)
advance='    <button onclick="show(\'advances\',this)">Avans Takip</button>\n'
if advance not in s:
    raise RuntimeError('Avans button not found')
s=s.replace(advance,'',1)
anchor='<div class="nav-group" id="adminNavGroup" style="display:none">'
if anchor not in s:
    raise RuntimeError('Management nav anchor not found')
finance='''<!-- SAMA_FINANCE_NAV_V1 -->
<div class="nav-group">
  <button class="nav-group-title" onclick="toggleNavGroup(this)">MUHASEBE & FİNANS <span>▸</span></button>
  <div class="nav-group-items">
    <button onclick="show('advances',this)">Avans Takip</button>
  </div>
</div>

'''
s=s.replace(anchor,finance+anchor,1)
p.write_text(s,encoding='utf-8')
print('moved Avans Takip to MUHASEBE & FİNANS')
