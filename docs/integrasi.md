# Panduan instalasi dan integrasi TitikLapar

Panduan ini menjelaskan implementasi aplikasi yang tersedia pada 30 Oktober 2026. Jalankan perintah dari direktori utama proyek, tempat `manage.py` berada. Contoh terminal menggunakan PowerShell di Windows.

- [Ringkasan proyek dan pembagian modul](../README.md)
- [Aplikasi di PWS](https://justin-evan-titiklapar.pws.cs.ui.ac.id/)
- [Panduan pengujian SharedPost](../SharedPost/TESTING.md)
- [Keamanan SharedPost](../SharedPost/SECURITY.md)
- [Panduan build CSS](../assets/css/README.md)

## 1. Instalasi lokal

Lingkungan pengembangan dan pengujian proyek memakai Python 3.12, Django 5.2, serta SQLite untuk lokal. Deployment menggunakan PostgreSQL. Dependensi aplikasi tercantum dalam [requirements.txt](../requirements.txt), sedangkan alat pengujian tersedia dalam [requirements-dev.txt](../requirements-dev.txt).

Untuk salinan proyek baru:

```powershell
git clone https://github.com/Projek-PBP-B-12/ProjekUTSPBP.git
cd ProjekUTSPBP
python -m venv env
.\env\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Jika virtual environment sudah tersedia, cukup aktifkan lingkungan tersebut. Jika aktivasi PowerShell tidak tersedia, gunakan `.\env\Scripts\python.exe` sebagai pengganti `python` pada perintah berikutnya.

Buat konfigurasi lokal tanpa menimpa `.env` yang sudah ada:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Aplikasi membaca `.env` di direktori utama. Untuk lokal, gunakan nilai dari [.env.example](../.env.example):

```dotenv
PRODUCTION=False
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SITE_URL=http://127.0.0.1:8000
```

Dengan `PRODUCTION=False`, aplikasi menggunakan SQLite dan mendukung HTTP lokal. Konfigurasi email console menampilkan isi email di terminal; tidak mengirimkannya ke inbox.

Siapkan database dan jalankan aplikasi:

```powershell
python manage.py migrate
python manage.py check
python manage.py runserver
```

Buka [aplikasi lokal](http://127.0.0.1:8000/), daftar akun, lalu login. Akun admin bersifat opsional dan dapat dibuat melalui `python manage.py createsuperuser`.

## 2. Hubungan antar modul

| Modul | Data dan tanggung jawab | Hubungan dengan modul lain |
| --- | --- | --- |
| UserProfile | Registrasi, login/logout, profil, kontak WhatsApp/Line, dan lokasi bawaan. Email pengingat disimpan pada `User.email`. | Profil menunjuk satu Location milik pengguna. SharedPost mengarahkan pencari ke kontak donor. Notification memakai email pemilik makanan. |
| FoodItem | Inventori pribadi: nama, kategori, tanggal beli/kedaluwarsa, URL foto, dan status makanan. | Menjadi sumber data makanan untuk SharedPost dan pengingat Notification. |
| SharedPost | Penawaran makanan: makanan, lokasi pengambilan, petunjuk, dan status aktif. | Menghubungkan FoodItem dengan Location; mengubah status makanan saat publikasi, penghapusan, atau penyelesaian penawaran. |
| Location | Lokasi tersimpan milik pengguna, koordinat, geocoding Nominatim, serta peta Leaflet/OpenStreetMap. | Dipilih secara eksplisit untuk penawaran. Lokasi bawaan profil menentukan pusat peta dan acuan jarak/radius. |
| Notification | Riwayat pengingat H-7, H-3, H-1, status baca, dan hasil pemrosesan email. | Pengingat mengacu pada pemilik, makanan, dan tanggal kedaluwarsa. |

Data pribadi dikelola berdasarkan pengguna yang sedang login. Kontrol kepemilikan diperiksa di server, termasuk jika permintaan dikirim langsung tanpa memakai tombol antarmuka.

## 3. Alur penggunaan dari akun baru

1. Daftar akun dengan email, kemudian login.
2. Buka Profil dan isi kontak donor jika ingin membagikan makanan. WhatsApp memakai kode negara tanpa `+` atau spasi; Line disimpan sebagai ID.
3. Buka Lokasi tersimpan dan tambahkan lokasi pengambilan. Koordinat dapat diisi manual, dicari melalui nama area, atau diisi melalui GPS setelah izin diberikan. Pencarian/GPS hanya mengisi formulir; tekan **Simpan lokasi** untuk menyimpan.
4. Pilih lokasi bawaan jika ingin memakai pusat peta pribadi, jarak, radius, dan urutan Terdekat. Pilihan ini tidak mengganti lokasi pengambilan pada penawaran yang sudah ada.
5. Buka Makananku, lalu **Tambah makanan**. Nama dan kategori diisi melalui formulir. Tanggal beli dan kedaluwarsa yang dikosongkan memakai tanggal hari ini; tidak ada estimasi ketahanan makanan atau pengisian nama dari Open Food Facts.
6. Buka **Detail** makanan untuk mengedit, menandai habis, menyimpan kembali, menghapus, atau membagikan makanan yang memenuhi syarat.
7. Buat penawaran dengan memilih makanan dan lokasi milik sendiri, lalu isi petunjuk pengambilan sepanjang 10–1.000 karakter setelah spasi tepi dibuang.
8. Pengguna lain membuka penawaran melalui papan atau peta. **Klaim** membuka detail; **Hubungi donor** membuka kontak. Kesepakatan pengambilan dilakukan langsung antar pengguna. Klaim belum merupakan reservasi otomatis.
9. Setelah makanan diambil, pemilik menekan **Tandai Sudah Diambil**.

## 4. Status makanan, penawaran, dan penghapusan

| Aksi | Status FoodItem | Keadaan SharedPost |
| --- | --- | --- |
| Menambahkan makanan | `STORED` / Tersimpan | Belum ada penawaran. |
| Membuat penawaran | `OFFERED` / Ditawarkan | Penawaran aktif; tampil jika makanan belum kedaluwarsa dan akun pemilik aktif. |
| Menghapus penawaran aktif | `OFFERED` menjadi `STORED` | Penawaran tersebut dihapus; makanan tetap ada. |
| Tandai Sudah Diambil | `CONSUMED` / Sudah habis | Penawaran dinonaktifkan dan tidak tampil di papan/peta publik. |
| Menandai makanan habis dari Makananku | `CONSUMED` | Penawaran aktif makanan ikut dinonaktifkan. |
| Simpan kembali | `STORED` | Penawaran aktif ditutup. Riwayat penawaran tidak otomatis diaktifkan kembali. |
| Menghapus makanan | Makanan dihapus | Penawaran yang terkait ikut dihapus melalui relasi `CASCADE`. |

Satu makanan hanya boleh mempunyai satu penawaran aktif, tetapi dapat memiliki beberapa riwayat penawaran nonaktif. Untuk menawarkan makanan kembali setelah **Simpan kembali**, buat penawaran baru melalui **Bagikan**.

### Aturan kedaluwarsa

- Perhitungan menggunakan tanggal server pada zona waktu `Asia/Jakarta`.
- Makanan dianggap kedaluwarsa jika tanggalnya **lebih kecil** dari hari ini. Makanan dengan tanggal kedaluwarsa hari ini masih dapat ditawarkan.
- Setelah tanggal lewat, pembacaan berikutnya menyaring makanan tersebut dari papan dan peta publik. Pergantian hari tidak otomatis menghapus baris makanan atau penawarannya.
- Pemilik masih dapat membuka detail penawaran yang tidak tersedia; pengguna lain mendapat 404.
- Mengedit makanan menjadi kedaluwarsa menonaktifkan penawaran aktif. Mengubah tanggal makanan yang sebelumnya kedaluwarsa ke masa depan juga tidak otomatis menerbitkan ulang penawaran.

### Dampak pada lokasi, notifikasi, dan akun

- Lokasi yang masih direferensikan penawaran, termasuk riwayat nonaktif, tidak dapat diedit/dihapus melalui alur pengelolaan lokasi. Tambahkan lokasi baru untuk mengganti titik pengambilan.
- Menghapus makanan mempertahankan riwayat notifikasi; referensi makanannya menjadi kosong (`SET_NULL`). Menghapus penawaran tidak menghapus notifikasi.
- Antarmuka notifikasi menyediakan daftar dan **Tandai sudah dibaca**. Belum tersedia fitur hapus notifikasi satu per satu.
- Penghapusan akun memerlukan kata sandi saat ini dan konfirmasi, lalu menghapus data milik akun yang terkait. Data pengguna lain tidak ikut dihapus.

## 5. Papan, foto, dan integrasi peta

Papan menyediakan pencarian nama makanan/area, kategori sesuai pilihan model FoodItem, tab Semua Penawaran/Penawaran Saya, radius 1/2/5/10 km atau Semua area, serta sorting Terdekat/Terbaru. Tanpa lokasi bawaan, radius dan Terdekat dinonaktifkan; server memakai Terbaru.

Daftar awal menampilkan enam penawaran. **Lihat lebih banyak penawaran** menampilkan hasil kumulatif berikutnya dengan mempertahankan filter. Mengganti filter mereset halaman.

HTMX memperbarui formulir dan daftar menggunakan partial HTML. Request biasa menggunakan halaman lengkap. Hapus dan selesai memakai optimistic UI: kartu segera disembunyikan, lalu hasil server mengonfirmasi perubahan. Jika permintaan gagal, antarmuka memulihkan kartu dan menyediakan umpan balik.

### Foto

- Form foto menerima HTTP/HTTPS. Tautan berbagi Google Drive tetap dapat disimpan.
- Dialog Makananku menyediakan **Buka foto ↗** menuju URL asli di tab baru. Tautan disembunyikan jika URL kosong atau tidak didukung.
- Kartu, detail SharedPost, dan data pin memakai normalisasi beberapa format URL Google Drive menjadi thumbnail.
- Normalisasi tidak mengubah izin akses file. Foto privat, URL rusak, atau tautan halaman HTML dapat gagal ditampilkan; kartu/detail memakai placeholder dan popup peta menampilkan **Foto tidak tersedia**.
- Validasi format URL tidak menjamin isinya gambar atau selalu tersedia.

### Peta dan layanan eksternal

Lokasi publik dibulatkan ke tiga angka desimal. Radius dan jarak memakai titik area publik yang sama, sehingga angka menunjukkan perkiraan jarak geografis, bukan rute perjalanan. Pengguna tetap perlu menyepakati titik temu melalui kontak donor.

**Lihat lokasi/Lihat peta** membawa ID penawaran ke halaman peta agar pin yang sesuai dibuka. Penawaran pada koordinat publik sama dikelompokkan menjadi satu pin; seluruh penawaran dapat dibuka dari popup yang bisa digulir.

Nominatim digunakan untuk mencari area di Indonesia. Hasil pencarian disimpan melalui cache Django selama 24 jam dan akses layanan memakai timeout. Kegagalan layanan menghasilkan pesan kesalahan; input koordinat manual tetap tersedia pada pengelolaan lokasi. Untuk deployment dengan beberapa worker, konfigurasi cache bersama perlu disiapkan oleh pengelola server.

## 6. Pengingat dan pengiriman email

Pengingat dibuat untuk makanan `STORED` atau `OFFERED` milik akun aktif ketika sisa hari tepat **7, 3, atau 1 hari**. Penyimpanan makanan menjadwalkan pemrosesan pengingat makanan tersebut setelah transaksi berhasil. Membuka halaman Notifikasi dapat membuat pengingat yang memenuhi syarat, tetapi tidak menjalankan pengiriman email.

Untuk memeriksa jumlah makanan yang memenuhi syarat tanpa mengubah database atau mengirim email:

```powershell
python manage.py send_food_reminders --dry-run
```

Untuk membuat pengingat dan memproses email yang menunggu/gagal:

```powershell
python manage.py send_food_reminders
```

Perintah kedua dapat memproses pengingat pengguna lain yang memenuhi syarat di database tersebut. Di server, jadwalkan perintah ini setiap hari menggunakan scheduler deployment. Keberadaan command di repositori tidak otomatis memasang jadwal.

Untuk pengiriman ke inbox, isi environment SMTP melalui panel PWS dan gunakan `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`. Variabel yang tersedia meliputi `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_TIMEOUT`, dan `DEFAULT_FROM_EMAIL`. Pilih kombinasi port/TLS/SSL sesuai penyedia email; jangan mengaktifkan TLS dan SSL bersamaan.

`SITE_URL` harus menunjuk domain PWS agar tautan dalam email tidak mengarah ke localhost. Status email diterima backend belum membuktikan email sudah masuk inbox. Periksa folder spam dan hasil pengiriman layanan email bila diperlukan. Kredensial SMTP tidak disimpan dalam repositori.

## 7. Migrasi dan pengujian

Jalankan migrasi setelah mengambil kode terbaru dan sebelum memakai versi baru pada database:

```powershell
python manage.py migrate
python manage.py migrate --check
python manage.py makemigrations --check --dry-run
```

Gunakan migrasi yang sudah disertakan proyek. Perubahan dokumentasi, template, CSS, dan JavaScript tidak memerlukan migrasi baru. Pemeriksaan `makemigrations --check --dry-run` mendeteksi perubahan model yang belum memiliki migrasi tanpa membuat berkas baru.

Untuk menyiapkan tes lengkap:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python manage.py check
python manage.py test --noinput
```

Tes membuat database dan akun sementara sendiri. Tidak perlu menjalankan `runserver`. Jika ingin memakai Edge yang sudah terpasang untuk tes browser:

```powershell
$env:BROWSER_CHANNEL = "msedge"
python manage.py test --noinput
```

Petunjuk menjalankan tes SharedPost dan coverage tersedia dalam [TESTING.md](../SharedPost/TESTING.md). Skenario mencakup kepemilikan, validasi, perubahan status, filter/pagination, CSRF, pembatasan frekuensi, optimistic UI, kegagalan permintaan, dan navigasi antar modul.

Saat verifikasi pengembangan pada 30 Oktober 2026, seluruh **313 tes** aplikasi lulus. Ini hasil satu versi kode, bukan jaminan seluruh kemungkinan masalah telah ditemukan. Tes lokal menggunakan SQLite dan simulasi layanan pada beberapa skenario; pengiriman SMTP nyata, tile peta, serta request bersamaan pada PostgreSQL perlu pemeriksaan deployment tersendiri.

### Pemeriksaan manual setelah deployment

Gunakan dua akun uji dengan sesi browser terpisah. Periksa registrasi/login, makanan dan lokasi, publikasi/edit/hapus/selesai penawaran, Klaim/kontak, akses antar akun, peta bertumpuk, foto gagal dimuat, tampilan mobile, dan logout. Periksa makanan kedaluwarsa hari ini serta tanggal yang sudah lewat. Untuk pagination, siapkan lebih dari enam penawaran yang lolos filter.

Pengujian PWS pada 30 Oktober 2026 telah memeriksa alur utama menggunakan dua akun sementara dan membersihkan data uji setelahnya. Pengiriman email nyata, scheduler, pagination lebih dari enam penawaran, serta pencarian Nominatim/GPS belum diverifikasi langsung dalam sesi tersebut.

## 8. Deployment PWS

Gunakan [.env.prod.example](../.env.prod.example) sebagai referensi. Isikan nilai sebenarnya melalui environment server; file contoh tidak otomatis dibaca.

| Variabel | Konfigurasi produksi |
| --- | --- |
| `PRODUCTION` | `True`, untuk memilih PostgreSQL dan cookie HTTPS. |
| `DEBUG` | `False`. |
| `SECRET_KEY` | Kunci acak yang disimpan di environment server. Aplikasi menolak mode produksi jika kosong. |
| `DB_NAME`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `SCHEMA` | Sesuai database dan schema PWS yang digunakan. |
| `ALLOWED_HOSTS` | Nama domain tanpa skema, misalnya `justin-evan-titiklapar.pws.cs.ui.ac.id`. |
| `CSRF_TRUSTED_ORIGINS` | Origin lengkap: `https://justin-evan-titiklapar.pws.cs.ui.ac.id`. |
| `SITE_URL` | URL HTTPS PWS untuk tautan aplikasi/email. |
| Konfigurasi email | Sesuai penyedia SMTP; mode console hanya mencetak email ke log. |

Gunakan `SECRET_KEY` yang tetap untuk deployment; pergantian kunci membuat pengguna perlu login ulang. Jangan commit `.env`, password database, atau kredensial SMTP/PWS.

Workflow [push-pws.yml](../.github/workflows/push-pws.yml) dipicu oleh push ke **`pws-branch`**. Workflow menggunakan GitHub Actions secrets `PWS_USERNAME` dan `PWS_PASSWORD` untuk mendorong branch ke remote PWS.

Alur integrasi kelompok:

1. Commit dan push perubahan pada branch pengerjaan.
2. Buat PR ke `main`, tinjau, lalu merge.
3. Integrasikan `main` ke `pws-branch` melalui PR.
4. Pastikan workflow deployment berhasil dan build/start aplikasi di PWS selesai.
5. Pastikan proses deployment menjalankan:

```powershell
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
```

6. Uji login dan pengiriman formulir melalui domain HTTPS PWS. Merge ke `main` saja tidak memicu workflow PWS.

Kepercayaan header reverse proxy, redirect HTTPS, dan HSTS perlu disesuaikan dengan konfigurasi PWS oleh pengelola server. Jangan menganggap hasil tes lokal sudah memverifikasi konfigurasi environment produksi.

## 9. Penelusuran masalah umum

| Gejala | Pemeriksaan |
| --- | --- |
| CSRF 403 dengan alasan origin tidak dipercaya | Pastikan domain HTTPS benar di `CSRF_TRUSTED_ORIGINS`, deployment sudah memakai konfigurasi terbaru, lalu muat ulang formulir setelah login. |
| Kode GitHub baru tetapi tampilan PWS lama | Periksa apakah perubahan sudah masuk `pws-branch`, workflow/build berhasil, dan static files sudah dikumpulkan. |
| Foto tampil di Makananku sebagai tautan tetapi gagal pada kartu | Periksa apakah URL berisi gambar yang dapat diakses publik. Tautan membuka halaman asli; pratinjau memerlukan respons gambar. |
| Radius/Terdekat dinonaktifkan | Pilih lokasi bawaan milik akun melalui Lokasi tersimpan atau edit profil. |
| Makanan tidak tersedia saat membuat penawaran | Pastikan milik akun, berstatus `STORED`, belum lewat kedaluwarsa, dan tidak punya penawaran aktif. |
| Lokasi tidak dapat dihapus | Periksa penawaran aktif atau riwayat penawaran yang masih mereferensikannya. |
| HTTP 429 saat mengubah penawaran | Tunggu sesuai `Retry-After`. Batas bawaan gabungan aksi SharedPost adalah 20 percobaan POST per akun dalam 60 detik; membaca daftar tetap tersedia. |
| Notifikasi ada tetapi email tidak masuk | Periksa SMTP, alamat email profil, tahap H-7/H-3/H-1, status hasil pengiriman, dan scheduler harian. Backend console tidak mengirim ke inbox. |

## 10. Dokumentasi penggunaan AI

Dokumentasi penggunaan AI untuk SharedPost tersedia pada [AI_DISCLOSURE.md](../SharedPost/AI_DISCLOSURE.md). Catat bantuan AI, peninjauan pengguna, perbaikan, dan batas verifikasi sesuai proses yang benar-benar dilakukan. Panduan integrasi ini mendeskripsikan perilaku kode; pembagian kontribusi setiap anggota tetap didokumentasikan oleh penanggung jawab modul masing-masing.
