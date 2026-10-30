# Styling bersama dan Tailwind

Layout `templates/base.html` memakai Tailwind CSS 4.3.3 yang dikompilasi ke
`static/css/app.css`. Edit **`assets/css/app.tailwind.css`**, lalu jalankan:

```powershell
python tools/build_sharedpost_css.py --page app
```

Tambahkan `--watch` untuk membangun ulang selama pengeditan. Compiler standalone,
checksum, dan cara menyiapkannya dijelaskan dalam
[panduan styling SharedPost](../../SharedPost/STYLING.md#build-lokal).
Pilihan build lainnya tetap tersedia:

```powershell
python tools/build_sharedpost_css.py --page sharedpost
python tools/build_sharedpost_css.py --page dashboard
python tools/build_sharedpost_css.py --page fooditem
```

Halaman Makananku memakai `assets/css/fooditem.tailwind.css` dengan prefix `fi`
dan selector `.inventory-page`. Hasil build-nya adalah `static/css/fooditem.css`.
Sidebar tetap memakai layout bersama; styling inventori tidak mengubah modul lain.

Commit sumber CSS dan hasil build. Deployment cukup memakai hasil CSS yang sudah
dikompilasi; tidak membutuhkan npm atau compiler Tailwind saat aplikasi berjalan.
Naikkan parameter versi CSS di `templates/base.html` ketika hasil `app.css` berubah.

## Menjaga kompatibilitas tampilan

- Utility Tailwind diterapkan lewat `@apply` pada selector yang sudah digunakan
  template (`.sidebar`, `.app-main`, `.button`, dan lainnya). Nama kelas dan blok
  template tetap tersedia untuk modul lain.
- Preflight tidak diimpor agar default elemen HTML tetap mengikuti perilaku lama.
- Nilai warna, font, ukuran dalam piksel, breakpoint `max-width: 800px`, dan urutan
  aturan dipertahankan. Aturan komponen tetap di luar layer agar prioritasnya sama.
- Prefix `app` membedakan sumber layout bersama dari `sp` (SharedPost) dan `db`
  (dashboard). CSS modul tetap dimuat sesudah CSS bersama.
- Shorthand font, background, border, serta aturan yang perlu nilai persis tetap
  ditulis sebagai CSS. Hindari menambahkan variabel `--tw-leading` atau
  `--tw-font-weight` pada tombol bersama karena utility modul lain membacanya.
- `static/css/app.css` adalah hasil build. Jangan mengeditnya langsung.

Halaman notifikasi juga mewarisi `base.html`. CSS notifikasi mengatur kontennya,
sedangkan sidebar dan tombol Keluar memakai komponen bersama. Dashboard memakai
footer sidebar yang sama: tombol Keluar berjarak 24px setelah menu navigasi.
Kelas `sidebar-logout-button` menjaga tampilannya dari override tombol setiap modul.
Halaman profil, edit profil, kontak donor, dan hapus akun juga memakai layout ini
melalui `userprofile/base.html`. CSS profil mengatur konten akun tanpa memuat reset
landing page atau menggandakan navigasi. Landing page, login, dan registrasi tetap
memakai layoutnya sendiri.

## Menu mobile bersama

Pada lebar maksimal 800px, semua halaman yang mewarisi `base.html` memakai header
dan tombol Menu yang sama. Styling berasal dari `app.tailwind.css`, sedangkan
`static/js/app-menu.js` mengatur buka/tutup, backdrop, Escape, fokus keyboard,
penguncian konten di belakang menu, dan perubahan ukuran layar. Script bersama
dimuat di luar blok `extra_js`, sehingga tetap tersedia pada modul yang mengganti
blok tersebut. Dashboard dan SharedPost tidak lagi membuat menu sendiri.

Jika JavaScript tidak tersedia, navigasi mobile tetap ditampilkan tanpa drawer.
Saat menu terbuka pada mobile, fokus tetap di dalam menu; menutupnya mengembalikan
fokus ke tombol Menu. Pada desktop, sidebar kembali terlihat dan konten dapat
digunakan seperti biasa.
