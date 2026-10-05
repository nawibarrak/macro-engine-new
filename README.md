# Macro Engine Desk + feed otomatis
index.html = web tool. scripts/fetch_feed.py = tarik FRED/CFTC/MOVE -> data/feed.json.
.github/workflows/feed.yml = jalan tiap 30 menit, lalu publish ke GitHub Pages.
Kunci FRED: GitHub > Settings > Secrets and variables > Actions > FRED_API_KEY (jangan di kode).

## Lapisan analisis
- scripts/estimate_betas.py: beta aset diestimasi mingguan (ridge ke prior, uji walk-forward). Dipakai hanya jika lolos.
- Sinyal BUY/SELL/HOLD di web: hanya keluar bila audit bersih, konsensus asli >=60%, skor >=0.75, keyakinan >=60%.
- Probabilitas L2 otomatis: workflow `prob-l2` (bulanan) menjalankan scripts/l2_probability.py. Secrets: FRED_API_KEY, KAGGLE_USERNAME, KAGGLE_KEY (atau KAGGLE_API_TOKEN). Zona waktu data harga dideteksi otomatis; bila tidak terverifikasi, hasil tidak ditulis.

## Lapisan data v2
scripts/registry.py = daftar semua seri (label, frekuensi, penyedia berlapis, batas wajar).
scripts/data_layer.py = ambil semua seri -> data/series/<ID>.json dan data/status.json
(status per seri: ok / basi / ditahan / gagal / mati, plus gerbang sinyal). Riwayat seri disimpan
di cache Actions, bukan di git. Seri bertanda unverified di status.json belum teruji: cek run pertama.

## Beranda v2 (tahap 2)
index.html = Beranda baru (membaca data/bundle.json, data/status.json, data/feed.json, data/consensus.csv).
lanjutan.html = alat lama (sinyal, input manual). bundle.json dibuat oleh scripts/data_layer.py,
jadi beranda kosong sampai workflow feed-dan-deploy selesai sekali dengan skrip terbaru.

## Audit dan penjaga konsep (tahap 2b)
- `scripts/pipeline.py` adalah satu-satunya pintu workflow; langkah baru ditambah di daftar STEPS.
- `scripts/audit_series.py` -> `data/audit_series.json`: uji silang antar-sumber, identitas internal, deteksi macet. Gerbang sinyal tertutup bila seri kritis bermasalah.
- `scripts/check_concept.py --strict` memeriksa kepatuhan pada `docs/KONSEP.md`; wajib hijau sebelum setiap penyerahan.
