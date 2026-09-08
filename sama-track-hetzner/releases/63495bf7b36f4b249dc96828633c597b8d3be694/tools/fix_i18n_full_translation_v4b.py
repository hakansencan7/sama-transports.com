from pathlib import Path

src=Path('tools/fix_i18n_full_translation_v4.py').read_text(encoding='utf-8')
src=src.replace("fn_start=s.find('  function translateString(raw,l){')", "fn_start=s.find('  function translateString(value,l){')")
exec(compile(src,'tools/fix_i18n_full_translation_v4.py','exec'))
