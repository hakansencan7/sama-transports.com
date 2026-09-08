# SAMA TRACK V61 - Web Deploy

Bu klasor SAMA TRACK V61 uygulamasinin Render uzerinde test edilmesi icin hazirlanmistir.

## Yerelde calistirma

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Tarayici: http://127.0.0.1:8000

## Render

1. Bu klasoru bir GitHub reposuna yukleyin.
2. Render > New > Blueprint secin.
3. Repo'yu secin. `render.yaml` ayarlari otomatik okunur.
4. Deploy tamamlaninca Render size HTTPS adresi verir.

## Veri kaliciligi uyarisi

Uygulama su anda SQLite (`sevkiyat.db`) kullaniyor. Render'in gecici dosya sisteminde DB yeniden deploy/restart sonrasi kaybolabilir. Bu paket TEST icindir. Kalici canli kullanim icin PostgreSQL veya Render Persistent Disk'e gecilmelidir.
