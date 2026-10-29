# Pengujian SharedPost

## Persiapan

Aktifkan virtual environment proyek, lalu instal dependensi pengujian:

```powershell
python -m pip install -r requirements-dev.txt
```

Tes browser memakai Playwright dan Chromium secara default. Pasang browser dengan `python -m playwright install chromium`. Tidak perlu menjalankan `runserver`: Django menyediakan server pengujian dan database sementara sendiri. Akun, sesi login, lokasi, dan makanan contoh dibuat otomatis, sehingga tes tidak membutuhkan akun atau data inventori lokal. Sesi login disiapkan oleh Django; tes ini tidak menguji halaman login milik modul lain.

## Perintah

Backend saja:

```powershell
python manage.py test SharedPost.tests SharedPost.test_services SharedPost.test_board SharedPost.test_map_link SharedPost.test_migrations SharedPost.test_rate_limit
```

Browser saja:

```powershell
python manage.py test SharedPost.test_browser
```

Semua tes modul:

```powershell
python manage.py test SharedPost
```

Coverage Python backend:

```powershell
python -m coverage run manage.py test SharedPost.tests SharedPost.test_services SharedPost.test_board
python -m coverage report -m
```

Pengukuran coverage mengecualikan berkas tes dan migrasi. Coverage Python tidak mengukur JavaScript atau ketepatan visual desain.

## Pilihan browser

Untuk memakai Chromium milik Playwright, instal browser (Chromium sudah menjadi pilihan default):

```powershell
python -m playwright install chromium
$env:BROWSER_CHANNEL = "chromium"
python manage.py test SharedPost.test_browser
```

`BROWSER_CHANNEL=chrome` atau `BROWSER_CHANNEL=msedge` dapat memakai Chrome/Edge yang sudah terpasang. Di macOS/zsh gunakan `BROWSER_CHANNEL=chromium python manage.py test SharedPost.test_browser`. Untuk melihat browser selama tes, gunakan `$env:BROWSER_HEADLESS = "0"`; nilai default `1` menjalankannya tanpa jendela.

## Skenario browser

- Tambah, edit, hapus, dan tandai sudah diambil; tidak terjadi navigasi atau reload dokumen selama aksi HTMX.
- Pembatalan konfirmasi hapus/selesai tidak menghilangkan kartu atau mengirim POST.
- Optimistic UI hapus/selesai diuji dengan request ditahan sebelum mencapai server: kartu langsung tersembunyi dan jumlah berkurang, sedangkan data server belum berubah. Setelah request dilepas, HTML server mengonfirmasi keadaan akhir.
- Respons 403/404/500, kegagalan jaringan, timeout, pembatalan request, dan HTML tak terduga memulihkan kartu, jumlah, serta kontrol. Tombol Periksa ulang daftar membaca ulang data tanpa mengulang POST. Skenario kegagalan juga diuji pada mobile.
- Request filter lama dibatalkan saat aksi optimistic dimulai, pembaruan yang bersaing dicegah, dan nilai pencarian tetap tersimpan setelah respons berhasil.
- Rate limiting diuji dengan batas rendah di database sementara: respons 429 memulihkan optimistic UI, mempertahankan input tambah/edit, menyampaikan waktu tunggu, dan tetap mengizinkan pembacaan daftar. Pengaturan batas rendah hanya berlaku pada tes terkait.
- Pesan validasi server muncul tanpa menyimpan penawaran yang tidak valid; form bisa dibatalkan.
- Pencarian, kategori, tab penawaran sendiri, dan hasil kosong.
- Chip kategori menggunakan nilai kategori FoodItem; pilihan dan badge jumlah diperbarui tanpa reload.
- Radius dari lokasi bawaan dan jarak perkiraan pada kartu. Daftar selalu menampilkan penawaran terbaru lebih dulu; parameter sorting lama diabaikan dan tidak diteruskan pada tautan pagination.
- Tombol Lihat lebih banyak menambah enam kartu per tahap, mempertahankan filter, dan tidak menghasilkan duplikasi. Mengganti filter mereset halaman; menghapus penawaran tetap mempertahankan filter.
- Tombol Klaim membuka detail penawaran, lalu Hubungi donor membuka halaman kontak internal.
- Detail penawaran menyediakan Lihat lokasi menuju pin yang sesuai. Tes browser menggunakan stub API Leaflet untuk memeriksa pemusatan dan popup tanpa ketergantungan CDN; pemuatan peta/tile sungguhan tetap diperiksa terpisah.
- Penawaran pada koordinat publik yang sama dikelompokkan menjadi satu pin dengan jumlah yang benar. Semua tautan penawaran dapat diakses dari popup yang bisa digulir pada desktop dan mobile; penawaran yang dipilih dari detail tampil pertama. Judul/deskripsi berisi HTML tetap ditampilkan sebagai teks.
- Pengguna lain bisa melihat detail penawaran aktif tetapi tidak memiliki kontrol pemilik; request perubahan langsung ditolak dengan CSRF token yang valid.
- Menu dibuka/ditutup pada viewport 390 × 844; halaman dan form tidak melebar keluar layar.
- Tidak ada kesalahan JavaScript selama skenario pengujian.

Tes menggunakan data dan gambar lokal sementara, tanpa layanan eksternal. Ketersediaan URL foto eksternal, pengiriman pesan WhatsApp/Line, deployment, dan kesesuaian visual dengan Figma diperiksa terpisah. SQLite tidak membuktikan perilaku kunci baris atau request bersamaan pada PostgreSQL.

Tes backend pembatasan frekuensi mencakup kuota gabungan keempat aksi, akun dan sesi, pergantian jendela waktu, Retry-After, request yang tidak menghabiskan kuota, rollback inventori, dan konfigurasi tidak valid. Detail konfigurasi, migrasi, serta batas perlindungan tersedia di [SECURITY.md](SECURITY.md).
