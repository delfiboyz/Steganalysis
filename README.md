# Steganalysis Web App

Aplikasi web untuk mendeteksi steganografi LSB (Least Significant Bit) pada citra digital, dengan membandingkan dua algoritma steganalysis klasik:

- **Chi-Square Attack** (Westfeld, 2001) — menguji kesetaraan frekuensi pasangan nilai piksel (2k, 2k+1) pada histogram.
- **RS Analysis** (Fridrich, Goljan, Du, 2001) — mengklasifikasikan grup piksel menjadi Regular/Singular berdasarkan perubahan kehalusan lokal saat LSB di-flip dengan mask tertentu, lalu mengestimasi panjang pesan dari pergeseran simetri RM/SM.

## Menjalankan

```bash
source venv/bin/activate
pip install -r requirements.txt   # jika belum
python app.py
```

Buka `http://127.0.0.1:5000` di browser, unggah citra (PNG/BMP/TIFF/JPG), lalu klik "Analisis Citra".

Tidak ada file yang disimpan ke disk — seluruh analisis dilakukan di memori per-request.

## Struktur Proyek

```
app.py                     # Flask app & endpoint /analyze
algorithms/chi_square.py   # Implementasi Chi-Square Attack
algorithms/rs_analysis.py  # Implementasi RS Analysis
templates/index.html       # UI upload & hasil
static/css/style.css
static/js/main.js          # Fetch API + Chart.js untuk visualisasi
```

## Catatan Metodologis

Kedua algoritma dijalankan terpisah pada channel Grayscale, Red, Green, dan Blue, lalu hasilnya dibandingkan per channel. Verdict akhir:

- **Tinggi**: kedua metode sepakat mendeteksi indikasi LSB pada minimal satu channel.
- **Sedang**: hanya salah satu metode yang mendeteksi.
- **Rendah**: tidak ada indikasi dari kedua metode.

Chi-Square Attack diketahui lebih rentan terhadap false positive pada citra dengan histogram alami yang halus atau bertekstur tinggi (lihat Westfeld & Pfitzmann, 2001); RS Analysis umumnya lebih robust di berbagai jenis citra namun lebih berat secara komputasi. Hasil kedua metode sebaiknya dibaca sebagai indikasi statistik, bukan bukti pasti — ini adalah keterbatasan yang melekat pada teknik steganalysis klasik berbasis LSB (sudah tergantikan sebagian oleh metode statistik/ML modern untuk kasus produksi).
