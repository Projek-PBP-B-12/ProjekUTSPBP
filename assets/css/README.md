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
```

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

Migrasi layout bersama tidak mengubah stylesheet halaman yang berdiri sendiri,
seperti landing page dan notifikasi.
