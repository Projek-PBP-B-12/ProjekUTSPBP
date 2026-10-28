# Tailwind untuk SharedPost

SharedPost menggunakan Tailwind CSS 4.3.3. Layout kartu memakai grid responsif melalui kelas `sp:grid`, `sp:min-[481px]:grid-cols-2`, dan `sp:min-[1151px]:grid-cols-3`. Detail, spacing, foto, serta typography juga memakai utility Tailwind. Komponen berulang seperti tombol dan field form memakai `@apply`.

## Berkas yang diedit

- Template: `templates/SharedPost/`.
- Sumber CSS: `assets/css/sharedpost.tailwind.css`.
- Hasil build: `static/css/sharedpost.css`. Jangan edit hasil build langsung; perubahan akan tertimpa saat build berikutnya.

Preflight tidak diimpor. Utility dan variabel Tailwind memakai prefix `sp`, sedangkan selector komponen dibatasi ke `.sharedpost-page`. CSS hanya dimuat melalui `SharedPost/base.html`, yang tetap mewarisi `base.html` kelompok. Utility diberi prioritas `important` untuk mengatasi selector global milik `app.css` pada elemen SharedPost yang menggunakan kelas `sp:`.

## Filter dan kartu Papan Berbagi

Kategori ditampilkan sebagai chip dengan nilai pilihan FoodItem dan label Indonesia. Foto kartu memakai rasio 2:1. Tombol Klaim membuka detail penawaran, tempat pengguna dapat melanjutkan ke Hubungi donor; menekan Klaim tidak mengubah status makanan.

Radius (1, 2, 5, 10 km atau Semua area) dan urutan Terdekat memakai lokasi bawaan milik akun di Lokasi tersimpan. Jika lokasi belum dipilih, radius dan Terdekat dinonaktifkan, kartu menampilkan nama area, dan halaman menyediakan tautan pengaturan lokasi. Jarak menggunakan titik perkiraan yang sama dengan pin peta. Dengan lokasi bawaan, pilihan awal adalah radius 2 km dan Terdekat.

Daftar awal berisi maksimal enam penawaran. Lihat lebih banyak meminta halaman berikutnya melalui HTMX dan mengganti daftar dengan hasil kumulatif. Tautannya menyimpan seluruh filter. Nomor halaman dan badge jumlah disinkronkan lewat out-of-band swap; filter baru kembali ke halaman pertama. Tautan pagination menonaktifkan pewarisan `hx-include`, karena seluruh parameter sudah berada di URL.

Detail penawaran aktif menyediakan kartu Lokasi umum. Lihat lokasi membuka `Location:map?post=<id>` untuk menyorot pin perkiraan dan membuka popup penawaran tersebut. Tautan lama ke penawaran yang sudah tidak tersedia menampilkan pemberitahuan pada halaman peta.

Template SharedPost dan peta menyertakan parameter versi pada aset CSS/JS yang berubah agar browser meminta aset baru. Naikkan versinya ketika memperbarui berkas tersebut; hasil build CSS tetap harus ikut commit dan deployment.

## Build lokal

Compiler standalone resmi dipakai agar proyek Django tidak membutuhkan npm. Unduh Tailwind 4.3.3 dari rilis resminya sesuai sistem operasi:

https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.3.3

Untuk Windows x64, simpan executable sebagai `.tools/tailwindcss-v4.3.3-windows-x64.exe`, lalu jalankan:

```powershell
python tools/build_sharedpost_css.py
```

Untuk membangun ulang otomatis selama mengubah template/CSS:

```powershell
python tools/build_sharedpost_css.py --watch
```

Pada sistem operasi lain, gunakan executable resmi yang sesuai:

```text
python tools/build_sharedpost_css.py --compiler /path/to/tailwindcss
```

Compiler Windows yang disiapkan di proyek diperiksa menggunakan SHA-256. Compiler lokal tidak ikut Git; folder `.tools/` diabaikan. Template harus memuat nama utility lengkap agar terdeteksi saat build; jangan merangkai nama utility Tailwind dari potongan variabel Django.

## Build beranda setelah login

Beranda menggunakan compiler yang sama dengan prefix `db` dan CSS terpisah. Edit `templates/dashboard.html` atau `assets/css/dashboard.tailwind.css`, lalu bangun ulang `static/css/dashboard.css`:

```powershell
python tools/build_sharedpost_css.py --page dashboard
```

Tambahkan `--watch` untuk build otomatis. CSS beranda hanya dimuat ketika pengguna membuka Beranda dalam keadaan login.

## Commit dan deployment

Commit sumber CSS, template, skrip build, dan hasil CSS. PWS cukup menjalankan aplikasi Django dan collectstatic seperti sebelumnya; tidak perlu mengunduh atau menjalankan Tailwind saat deployment. Jika kelas Tailwind berubah, bangun ulang CSS sebelum commit.

## Verifikasi

```powershell
python manage.py test SharedPost
```

Tes browser memerlukan Playwright dan browser sesuai panduan `SharedPost/TESTING.md`.
