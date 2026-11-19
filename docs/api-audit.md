# Pemeriksaan kesesuaian alur web dan API

Pemeriksaan lokal: 19 November 2026, berdasarkan main `5e23016`.
Kelima API modul sudah digabungkan ke main. Catatan ini memuat hasil
pengujian lokal integrasi; deployment PWS dan integrasi Flutter belum diuji.

## Hasil pengujian

- 418 pengujian non-browser lulus, termasuk 95 pengujian API per modul dan lintas modul.
- `manage.py check`: tidak ada masalah.
- `manage.py makemigrations --check --dry-run`: tidak ada perubahan model.
- View, form, model, URL modul, template, dan JavaScript website lama tidak diubah.
  URL proyek hanya ditambah prefix `/api/`; pengaturan ditambah DRF dan token.
- Pengujian memakai database tes sementara. Pengujian callback pengiriman
  pengingat mengganti fungsi pengiriman email dengan mock.

## Aturan yang dibandingkan langsung dengan website

| Alur | Perilaku yang dipertahankan |
| --- | --- |
| Registrasi | Form RegistrationForm yang sama; hashing/validasi password Django, buat UserProfile |
| Akses akun | Wajib login; akun nonaktif ditolak; token dicabut saat logout API/hapus akun |
| Profil | Hanya profil sendiri; lokasi bawaan hanya milik sendiri; hapus akun wajib password dan konfirmasi |
| Kontak donor | Hanya username, WhatsApp, Line; email dan lokasi pribadi tidak dipublikasikan |
| Makanan | Tanggal kosong menjadi hari ini; tanggal kedaluwarsa tidak lebih awal dari tanggal beli; nama dibersihkan; foto HTTP/HTTPS |
| Penawaran baru | Form SharedPostForm yang sama; makanan STORED, belum kedaluwarsa, milik sendiri, tanpa penawaran aktif; lokasi milik sendiri |
| Makanan dibagikan | Status berubah menjadi OFFERED; satu penawaran aktif per makanan |
| Edit penawaran | Makanan tidak dapat diganti; lokasi harus milik sendiri; deskripsi minimal 10 karakter |
| Sudah diambil | Penawaran nonaktif dan makanan CONSUMED dalam transaksi yang sama |
| Hapus penawaran | Makanan OFFERED dari penawaran aktif kembali STORED |
| Status STORED/CONSUMED | Menonaktifkan penawaran yang aktif |
| Ubah tanggal kedaluwarsa | Penawaran ditutup bila makanan sebelumnya atau sesudah edit kedaluwarsa; tidak otomatis hidup kembali |
| Hapus makanan | Penawaran ikut dihapus; riwayat notifikasi tetap ada dengan food_item null |
| Lokasi | Koordinat divalidasi; lokasi yang pernah dipakai penawaran tidak bisa diedit; lokasi direferensikan tidak bisa dihapus |
| Peta | Hanya penawaran tersedia; lokasi dan makanan harus satu pemilik; koordinat publik dibulatkan; jarak dari lokasi bawaan sendiri |
| Notifikasi | Pengingat H-7/H-3/H-1 hanya milik sendiri dan tidak ganda; membuka daftar menghasilkan pengingat sebagaimana web |
| Email pengingat | Menggunakan callback _schedule_food_reminders yang sama setelah transaksi sukses |
| Pembatasan tulis | Web/API berbagi penghitung kuota SharedPost; semua metode tulis API diperiksa |
| CSRF/cache | Sesi web tetap memerlukan CSRF untuk perubahan; respons API pribadi tidak boleh disimpan cache |

Penguncian makanan dan penawaran memakai helper `_locked_post_and_food` milik
website. Perubahan status memakai `_change_status`, dan peta memakai
`get_map_pins`. Dengan demikian API menggunakan aturan yang sudah ada.

## Perbedaan antarmuka yang disengaja

API mengembalikan JSON, status HTTP, pagination DRF, dan memakai method REST
seperti PATCH/DELETE; website memakai HTML, form POST, redirect, dan HTMX.
Mobile memakai token; website tetap memakai session/cookie. Penolakan objek
tidak tersedia dapat berupa JSON 400/404 sesuai tindakan; tidak mengubah status
data. API pengelolaan data pribadi dibatasi ke pemilik, sementara kemampuan
moderasi admin pada endpoint website lama tetap tersedia.

Filter tampilan web seperti radius/urutan terdekat dan pemuatan kartu bertahap
tetap berjalan di website; API papan menyediakan pencarian, kategori, milik
sendiri, dan ordering sesuai `docs/api.md`. Kesamaan aturan bisnis bukan berarti
semua parameter atau format respons endpoint HTML dapat dipakai langsung di API.

## Batas verifikasi

Pengujian browser Playwright belum dijalankan pada pemeriksaan ini; dependensi
alat ujinya belum tersedia. Pengujian lokal memakai
SQLite, bukan PostgreSQL produksi; perilaku request serentak/row locking pada
PWS belum diuji. Koneksi SMTP nyata, deployment, dan integrasi Flutter juga
belum diuji. Hasil ini tidak merupakan jaminan bahwa seluruh lingkungan bebas bug.

## Mengulang pemeriksaan

```powershell
$apiTestModules = Get-ChildItem -Path FoodItem,Location,SharedPost,notification,userprofile,TitikLapar -Filter 'test*.py' |
    Where-Object { $_.Name -ne 'test_browser.py' } |
    ForEach-Object { $_.Directory.Name + '.' + $_.BaseName }
.\env\Scripts\python.exe manage.py test @apiTestModules --noinput
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Setelah Playwright tersedia, pengujian browser dapat dijalankan memakai Edge
yang terpasang, tanpa mengunduh Chromium tambahan:

```powershell
$env:BROWSER_CHANNEL = 'msedge'
.\env\Scripts\python.exe manage.py test FoodItem.test_browser Location.test_browser SharedPost.test_browser userprofile.test_browser TitikLapar.test_browser --noinput
```
