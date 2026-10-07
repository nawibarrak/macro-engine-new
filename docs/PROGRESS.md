# Progres (diperbarui tiap tahap; check_concept memeriksa angka seri)

Jumlah seri registry: 68

| Tahap | Status | Bukti | Belum terbukti |
|---|---|---|---|
| 1 Lapisan data v2 | Selesai, berjalan di GitHub | status.json run asli: 48 dari 50 seri ok (sebelum 17 seri baru) | 17 seri baru (barometer, COT, DefiLlama) belum diuji di data asli |
| 2 Beranda dan grafik | Dibangun, diuji dengan data uji | Render desktop/ponsel/gelap tanpa error JS | Belum dilihat dengan data asli di situs |
| 2b Audit data dan penjaga konsep | Dibangun: audit_series.py, check_concept.py, pipeline.py; hasilnya tampil di beranda (kepercayaan per seri, tabel uji, gerbang gabungan) | Diuji dengan sumber tiruan; pemeriksa konsep lolos uji mutasi (14 dari 14 pelanggaran terdeteksi) | Belum jalan di GitHub; toleransi adalah perkiraan awal |
| 3 Otak otomatis | Belum dimulai | | |
| 4 Probabilitas harian | Belum dimulai | | |
| 5 Keputusan dan jurnal | Belum dimulai | | |
| 6 Teknikal entry | Belum dimulai | | |

## Masalah terbuka
- Sinyal BUY/SELL/HOLD masih mesin lama di lanjutan.html (tidak sesuai K7, K8 sepenuhnya) sampai tahap 5.
- prob.yml dan l2_probability.py masih memakai Kaggle (melanggar K4) sampai tahap 4.
- Bank Indonesia belum ada (sumber BIS belum diuji).
- Jendela rilis rapat (5-10 menit setelah jam rilis) belum ada.

## Langkah berikutnya
Jalankan workflow dengan skrip terbaru, baca data/audit_series.json, perbaiki temuan, lalu mulai tahap 3.
