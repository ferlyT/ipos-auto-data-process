# 🚀 iPos 4.0 - Auto Data Closing Assistant (Auto Proses Data)

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

Aplikasi desktop otomasi cerdas (Floating Assistant Bot) untuk menjalankan siklus **Proses Data Bulanan (Januari s.d. Desember)** dan **Proses Tutup Tahun (Tutup Buku Tahunan)** secara penuh dan berulang pada software **Program Toko iPos 4.0** tanpa perlu intervensi manual berulang kali.

---

## 📌 Latar Belakang & Masalah
Pada aplikasi **iPos 4.0**, proses kalkulasi data persediaan dan jurnal akuntansi bulanan (terutama jika ada transaksi lintas tahun dalam jumlah besar) harus dijalankan satu per satu per bulan, diikuti dengan proses tutup tahun di setiap akhir Desember.
- Melakukan proses manual 12 bulan $\times$ multi-tahun memakan waktu berjam-jam dan rentan terhenti jika operator tidak menunggu di depan komputer.
- **iPos Auto Data Process** hadir sebagai asisten otomatis yang mengambil alih seluruh alur klik, pemilihan periode, konfirmasi modal, hingga penutupan buku tahunan secara mulus dan aman.

---

## 🌟 Fitur Utama

1. **Otomasi Siklus Lengkap Multi-Tahun**:
   - Menjalankan proses bulanan dari **Januari hingga Desember** secara sekuensial.
   - Otomatis beralih ke form **Proses Tutup Tahun** setiap kali bulan Desember selesai.
   - Otomatis melanjutkan ke **Januari tahun berikutnya** sampai rentang tahun akhir tercapai.

2. **Pencarian & Aktivasi Jendela Otomatis**:
   - Tidak perlu repot membuka tab menu *Proses Data* secara manual. Bot secara otomatis mencari jendela aktif iPos 4.0 di desktop, membawanya ke latar depan (*foreground*), dan mengklik tab **Proses Data**.

3. **Navigasi Dropdown Presisi**:
   - Menggunakan mekanisme *roll-up* 15x ke atas ke bulan Januari, lalu turun sesuai indeks bulan target.
   - Pilihan bulan dikunci menggunakan tombol `Enter` sehingga kursor **tidak melompat ke input Tahun**.
   - Input Tahun hanya disentuh pada bulan Januari; bulan Februari s.d. Desember dibiarkan tetap aman.

4. **Kepatuhan Aturan 'Perbaikan Stok'**:
   - Sesuai aturan iPos 4.0, opsi *Perbaikan Stok* hanya diizinkan pada bulan & tahun aktif saat ini.
   - Bot otomatis memvalidasi tanggal sistem: pada bulan-bulan lampau opsi ini dilewati agar tidak memicu error dari iPos, dan hanya dicentang pada periode aktif berjalan.

5. **Deteksi Selesai Deterministik (Anti-False-Positive)**:
   - Memantau kemunculan popup MessageBox OK (`Proses Bulanan Berhasil`) via Win32 API.
   - Memverifikasi status tombol `[ Tutup ]` melalui deteksi piksel ikon hijau aktif (>15 piksel hijau HSV) sebelum melangkah ke bulan berikutnya.

6. **Keamanan & Emergency Kill-Switch**:
   - **Tombol Pintas Darurat (`F12` atau `ESC`)**: Menghentikan otomasi seketika.
   - **PyAutoGUI Fail-Safe**: Mengarahkan kursor mouse ke pojok kiri atas monitor (`0, 0`) memutus kendali mouse secara instan.
   - **Jeda / Lanjutkan (Pause/Resume)**: Tombol `[⏸ JEDA]` untuk menghentikan sementara proses setelah bulan berjalan selesai.

7. **Asisten Kalibrasi Koordinat Visual**:
   - Dilengkapi tool `calibration.py` untuk menguji atau memperbarui koordinat target jika menggunakan tema Windows atau tata letak khusus.

---

## 🔄 Alur Kerja Otomasi (Workflow)

```mermaid
flowchart TD
    Start([Mulai Otomasi]) --> FindWin[Cari & Bawa iPos 4.0 ke Foreground]
    FindWin --> ClickTab[Klik Tab Menu 'Proses Data']
    ClickTab --> LoopYear[Mulai Siklus Tahun: Y]
    LoopYear --> OpenBulanan[Buka Form 'Proses Bulanan']
    
    OpenBulanan --> SelectMonth[Pilih Bulan M via Roll-Up & Enter]
    SelectMonth --> CheckJan{Apakah Bulan Januari?}
    CheckJan -- Ya --> SetYear[Isi Kotak Tahun Y]
    CheckJan -- Tidak --> CheckStock
    SetYear --> CheckStock{Opsi Perbaikan Stok Aktif & Periode Berjalan?}
    CheckStock -- Ya --> TickStock[Centang 'Perbaikan Stok']
    CheckStock -- Tidak --> ClickProses
    TickStock --> ClickProses[Klik Tombol [ Proses ]]
    
    ClickProses --> ConfirmYes[Konfirmasi Modal [ Yes ]]
    ConfirmYes --> WaitDB[Tunggu Kalkulasi Database Selesai]
    WaitDB --> CheckFinish{Popup OK / Tombol Tutup Aktif?}
    CheckFinish -- Belum --> WaitDB
    CheckFinish -- Ya --> AckOK[Konfirmasi Selesai & Tutup Popup]
    
    AckOK --> CheckDec{Apakah Selesai Desember?}
    CheckDec -- Tidak --> NextMonth[Lanjut Bulan M+1] --> SelectMonth
    CheckDec -- Ya --> CloseBulanan[Klik Tombol [ Tutup ] Bulanan]
    
    CloseBulanan --> OpenTahunan[Buka Form 'Proses Tutup Tahun']
    OpenTahunan --> SetYearTahunan[Isi Tahun Y & Klik [ Proses ]]
    SetYearTahunan --> ConfirmTahunan[Konfirmasi [ Yes ]]
    ConfirmTahunan --> WaitTahunan[Tunggu Proses Tutup Tahun Tuntas]
    WaitTahunan --> CloseTahunan[Klik Tombol [ Tutup ] Tahunan]
    
    CloseTahunan --> CheckEndYear{Tahun Y == Tahun Akhir?}
    CheckEndYear -- Tidak --> NextYear[Lanjut Tahun Y+1] --> LoopYear
    CheckEndYear -- Ya --> Done([Selesai 100%])
```

---

## 📁 Struktur Direktori

```
ipos-auto-data-process/
├── assets/                          # Template visual untuk fallback OpenCV
│   ├── btn_proses.png
│   ├── btn_tutup.png
│   ├── btn_yes.png
│   ├── header_bulanan.png
│   ├── header_tahunan.png
│   ├── label_periode.png
│   ├── label_proses_selesai.png
│   ├── ribbon_bulanan.png
│   └── ribbon_tahunan.png
├── calibration.py                   # Tool GUI kalibrasi & pengujian koordinat
├── config.json                      # Konfigurasi koordinat & timing tersimpan
├── config.py                        # Modul load/save konfigurasi
├── engine.py                        # Automation Engine (Multi-threaded & Win32)
├── gui.py                           # Floating Assistant Window (Tkinter Always-on-Top)
├── requirements.txt                 # Dependensi Python
├── run.bat                          # One-Click Windows Launcher
├── test_engine.py                   # Automated Test Suite (Dry-Run Simulation)
├── vision.py                        # OpenCV template matching & coordinate resolver
├── .gitignore
└── README.md
```

---

## 💻 Prasyarat & Instalasi

### 1. Prasyarat Sistem
- **Sistem Operasi**: Windows 10 / Windows 11 (32-bit atau 64-bit).
- **Python**: Versi 3.8 ke atas ([Download Python](https://www.python.org/downloads/)). Pastikan opsi **Add Python to PATH** dicentang saat instalasi.
- **Aplikasi Target**: Program Toko iPos 4.0 (Desktop).

### 2. Instalasi Dependensi
Buka Terminal atau PowerShell di dalam folder proyek, lalu jalankan:
```bash
pip install -r requirements.txt
```

Isi `requirements.txt`:
```txt
pyautogui>=0.9.54
opencv-python>=4.8.0
numpy>=1.24.0
pillow>=10.0.0
pywin32>=306
keyboard>=0.13.5
```

---

## 🚀 Cara Menjalankan

### Cara 1: Menggunakan Launcher Satu-Klik (Rekomendasi)
Klik ganda file:
```cmd
run.bat
```

### Cara 2: Menjalankan via Terminal / CMD / PowerShell
```cmd
python gui.py
```

---

## 📖 Panduan Penggunaan Langkah demi Langkah

1. **Buka Aplikasi iPos 4.0**:
   - Jalankan software iPos 4.0 dan login dengan hak akses Administrator.
   - Anda dapat membiarkannya di menu mana saja (bot akan otomatis membuka tab *Proses Data*).

2. **Buka iPos Auto Data Process**:
   - Jalankan `run.bat`. Jendela bot akan melayang (*Always-on-Top*) di layar monitor Anda.

3. **Konfigurasi Parameter**:
   - **Tahun Awal**: Pilih tahun awal siklus (misal: `2024`).
   - **Tahun Akhir**: Pilih tahun akhir siklus (misal: `2026`).
   - **Jalankan Proses Tahunan setiap selesai bulan Desember**: Centang opsi ini agar bot otomatis melakukan Tutup Buku Tahunan.
   - **Centang opsi 'Perbaikan Stok'**: Centang jika ingin perbaikan stok dijalankan (hanya akan aktif pada bulan & tahun berjalan saat ini).

4. **Mulai Eksekusi**:
   - Klik tombol **`[▶ MULAI OTOMASI]`**.
   - Bot akan memfokuskan jendela iPos 4.0, mengklik tab *Proses Data*, dan menjalankan siklus secara mandiri hingga selesai 100%.

5. **Kendali Saat Berjalan**:
   - **Jeda**: Klik tombol **`[⏸ JEDA]`** untuk menahan proses setelah bulan aktif selesai.
   - **Berhenti Darurat**: Tekan tombol **`F12`** atau **`ESC`** pada keyboard Anda kapan saja.

---

## 🎯 Tool Kalibrasi Koordinat (`calibration.py`)

Jika tampilan monitor Anda menggunakan scaling non-standar atau posisi jendela iPos telah dipindahkan:
1. Klik tombol **`⚙ Kalibrasi Posisi UI`** pada jendela bot, atau jalankan:
   ```cmd
   python calibration.py
   ```
2. Pilih elemen yang ingin dikalibrasi (misal: Dropdown Bulan, Tombol Proses).
3. Klik tombol **`[Ambil]`**, arahkan mouse ke posisi elemen pada iPos 4.0 selama hitungan mundur 3 detik.
4. Klik **`[💾 Simpan Pengaturan]`** untuk menyimpan koordinat baru ke `config.json`.

---

## 🛡️ Tips Keamanan & Rekomendasi
- **Backup Database Terlebih Dahulu**: Sangat disarankan untuk membuat salinan cadangan (*backup*) database iPos 4.0 sebelum menjalankan proses data tahunan dalam skala besar.
- **Hindari Intervensi Mouse/Keyboard**: Selama otomasi berjalan, hindari menggerakkan mouse secara acak agar koordinat klik tidak tergeser.
- **Fail-Safe**: Jika terjadi hal yang tidak diinginkan, cukup hentakkan kursor mouse ke pojok kiri atas monitor (`0, 0`) untuk mematikan bot seketika.

---

## 👤 Penulis & Lisensi
- **Repository**: [https://github.com/ferlyT/ipos-auto-data-process](https://github.com/ferlyT/ipos-auto-data-process)
- **Author**: ferlyT (<ferly.trianderi@gmail.com>)
- **Lisensi**: MIT License
