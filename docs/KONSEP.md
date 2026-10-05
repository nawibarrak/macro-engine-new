# Macro Engine Desk v2: kanon konsep

Berkas ini adalah acuan tunggal. Sesi mana pun (manusia atau AI) yang akan mengubah sistem WAJIB membacanya
bersama docs/PROGRESS.md sebelum menulis kode. Bila kode dan berkas ini bertentangan, yang salah adalah kode,
kecuali perubahan konsep sudah dicatat di "Log keputusan" di bawah SEBELUM kode diubah.

## Tujuan
Sistem analisis fundamental otomatis untuk satu trader: mengumpulkan data gratis, membersihkan, menganalisis,
lalu memberi bias BUY / SELL / HOLD per aset. Teknikal untuk titik entry baru ditambah SETELAH ada rekomendasi aksi (tahap 6).
Horizon: harian sampai mingguan. Aset prioritas sinyal: XAUUSD, WTI, S&P 500, USDJPY, EURUSD.
Berjalan di GitHub Pages + GitHub Actions (tanpa server): pembaruan near-real-time (menit), bukan tick.

## Tiga lapis (inti desain)
- TERUKUR: angka dari sumber. Selalu punya satuan, frekuensi, tanggal data, sumber, status.
- DISIMPULKAN: hasil hitungan sistem (fase, rezim, tekanan kebijakan, risiko pembalikan). Selalu menampilkan bukti dan ambang.
- DIPUTUSKAN: tindakan (BUY / SELL / HOLD) beserta gerbang yang lolos atau gagal dan jejak keputusan.
Tidak boleh ada kotak di layar yang mencampur ketiganya tanpa label.

## Invarian (aturan yang tidak boleh dilanggar)
Baris bertanda [uji] diperiksa otomatis oleh scripts/check_concept.py pada setiap run.
- K1 [uji] Setiap panel di index.html membawa satu label: TERUKUR, DISIMPULKAN, atau DIPUTUSKAN.
- K2 [uji] Beranda hanya-baca: tidak ada kolom input, textarea, atau select di index.html. Override manual hanya di lanjutan.html.
- K3 [uji] Setiap seri yang ditampilkan ada di scripts/registry.py dengan label, frekuensi, sumber berlapis, dan batas wajar (kecuali COT).
- K4 [uji] Pipeline utama tidak memakai Kaggle atau Colab. (Sisa lama: prob.yml dan l2_probability.py, diganti di tahap 4.)
- K5 [uji] Tidak ada singkatan sebagai label metrik makro: tulis "Pertumbuhan" dan "Inflasi", bukan G atau I.
- K6 Setiap kesimpulan menampilkan bukti pendukung dan ambang yang dipakai (berlaku dari tahap 3).
- K7 Semua ambang keputusan hidup di config/thresholds.json beserta alasan dan status pengujiannya. Tidak ada ambang tersembunyi di kode.
- K8 Bawaan adalah HOLD. Sinyal keluar hanya bila SEMUA gerbang lolos: gerbang data, audit silang-sumber, skor, keyakinan, kepastian rezim.
- K9 [uji] Proksi selalu berlabel "proksi". Angka yang tidak bisa diverifikasi tidak ditampilkan sebagai fakta.
- K10 Kata "terverifikasi" hanya boleh muncul bila ada bukti di data/audit_series.json.
- K11 [uji] Kunci API hanya di GitHub Secrets. Tidak ada kunci di berkas repo.
- K12 [uji] Perubahan konsep dicatat di Log keputusan sebelum kode berubah. docs/PROGRESS.md diperbarui tiap tahap dan jumlah seri-nya cocok dengan registry.
- K13 Keputusan berbasis aturan yang bisa diuji (backtest, jurnal, evaluasi 1/4/12 minggu), bukan penilaian LLM.
- K14 Kegagalan sumber tidak boleh diam-diam menghasilkan angka: data lama dipakai dan ditandai, atau seri ditahan.
- K15 Auto-pilot bisa dimatikan: ada tombol yang mengembalikan sistem menjadi agregator data murni (dibangun di tahap 5).

## Pipeline
sumber -> kumpulkan (penyedia berlapis, cache, asal data) -> bersihkan (satuan, vintage, batas wajar, lompatan) ->
audit (silang-sumber, konsistensi internal) -> fitur -> simpulkan -> putuskan -> beranda.
Semua langkah dijalankan scripts/pipeline.py (workflow cukup memanggil satu skrip itu; langkah baru ditambah di sana).
Aliran cepat (harga, yield, volatilitas, likuiditas harian) dan aliran lambat (makro, COT) dipisah: keputusan boleh
memakai nilai terakhir aliran lambat tanpa menunggu rilis berikutnya.

## Tahap dan kriteria selesai
1. Lapisan data v2: semua seri hijau, tiap angka punya sumber dan frekuensi.
2. Beranda dan grafik: kondisi pasar terbaca dari satu layar.
2b. Audit data: silang-sumber dan konsistensi internal, hasil tampil di beranda, gerbang menutup bila seri kunci gagal diaudit.
3. Otak otomatis: Fed reaction function, mesin fase dan skenario (Normal / Waspada / Stres / Krisis dengan histeresis), aliran modal terukur, skor risiko COT. Tidak ada input manual untuk analisis.
4. Probabilitas harian: L2 horizon harian dari yfinance dan FRED, tanpa Kaggle atau Colab. Hasil lulus atau gagal tampil.
5. Keputusan dan jurnal: gerbang baru, kepastian rezim, panel kontribusi tiap faktor, jurnal append-only, evaluasi 1/4/12 minggu, backtest bagian berbasis pasar, tombol auto-pilot off.
6. Teknikal untuk entry: hanya untuk aset yang sinyalnya BUY atau SELL.
Urutan wajib. Tahap berikutnya tidak dimulai sebelum tahap sebelumnya lulus audit dan check_concept bersih.

## Protokol setiap sesi
1. Baca berkas ini dan docs/PROGRESS.md. 2. Jalankan `python scripts/check_concept.py`. 3. Kerjakan SATU tahap.
4. Sebelum menyerahkan: jalankan uji, check_concept, dan perbarui PROGRESS.md (termasuk apa yang BELUM terbukti).
5. Bila perlu menyimpang dari konsep: tulis dulu di Log keputusan, minta persetujuan pemilik, baru ubah kode.

## Istilah
Seri = satu deret waktu di registry. Gerbang data = semua seri kunci segar dan lolos audit. Proksi = pengganti terdekat bila angka resmi tidak gratis.
Basi = lewat batas umur. Ditahan = lompatan ekstrem menunggu konfirmasi. Silang-sumber = membandingkan dua sumber independen untuk besaran yang sama.

## Log keputusan
- 2026-10-05 Pemilik menyetujui: L2 harian (menit-an hanya riset), aset prioritas XAUUSD/WTI/SPX/USDJPY/EURUSD, jeda 5-30 menit dari GitHub Actions diterima.
- 2026-10-05 Kaggle dan Colab dikeluarkan dari pipeline utama (K4).
- 2026-10-05 Masukan eksternal diadopsi: circuit breaker data, panel kontribusi faktor, label penuh tanpa singkatan, dua aliran cepat/lambat, tombol auto-pilot off.
- 2026-10-05 Audit data (tahap 2b) dikerjakan SEBELUM tahap 3 karena kesimpulan dan sinyal bergantung pada data. Kanon konsep dan pemeriksa otomatis ditambahkan atas permintaan pemilik agar konsisten antar sesi.
