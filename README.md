# Macro Engine Desk + feed otomatis
index.html = web tool. scripts/fetch_feed.py = tarik FRED/CFTC/MOVE -> data/feed.json.
.github/workflows/feed.yml = jalan tiap 30 menit, lalu publish ke GitHub Pages.
Kunci FRED: GitHub > Settings > Secrets and variables > Actions > FRED_API_KEY (jangan di kode).

## Lapisan analisis
- scripts/estimate_betas.py: beta aset diestimasi mingguan (ridge ke prior, uji walk-forward). Dipakai hanya jika lolos.
- Sinyal BUY/SELL/HOLD di web: hanya keluar bila audit bersih, konsensus asli >=60%, skor >=0.75, keyakinan >=60%.
