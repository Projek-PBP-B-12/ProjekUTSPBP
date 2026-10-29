# AI Disclosure — SharedPost / Papan Berbagi

Dokumen ini menjelaskan penggunaan AI dan kontribusi manual saya dalam pengembangan modul **SharedPost / Papan Berbagi** pada aplikasi TitikLapar.

**Tanggal penyusunan:** 29 Oktober 2026.  
**Alat:** OpenAI Codex melalui percakapan dan akses workspace proyek.  
**Acuan implementasi:** kode dalam repositori, desain, dan kebutuhan modul yang saya tentukan selama pengembangan.

## 1. Pernyataan penggunaan AI dan kontribusi manual

Saya menggunakan OpenAI Codex untuk membantu menyusun kerangka awal kode Python, template Django, CSS/Tailwind, JavaScript, tes otomatis, dan dokumentasi SharedPost. AI berfungsi sebagai asisten yang memberikan draf referensi dan saran struktur.

Setelah kerangka awal dihasilkan, saya melakukan penulisan ulang, penyesuaian logika, dan perbaikan kode secara manual. Saya menentukan kebutuhan dan desain, mencoba aplikasi, melakukan debugging, dan menulis langsung perbaikan untuk memastikan kode sesuai dengan standar integrasi kelompok. Penyesuaian UI/UX, pengelolaan state HTMX, dan penanganan edge case pada filter merupakan hasil perbaikan yang saya tulis manual dengan bantuan AI sebagai pemandu.

## 2. Ringkasan fitur dan kode

| Bagian | Implementasi yang tersedia | Berkas utama |
| --- | --- | --- |
| Model penawaran | Relasi FoodItem dan Location, deskripsi, status aktif, waktu pembuatan/perubahan, dan pembatasan satu penawaran aktif per makanan. Satu makanan tetap dapat memiliki beberapa riwayat penawaran nonaktif. | [models.py](models.py) |
| Form | Pilihan makanan milik pengguna yang masih tersimpan, belum kedaluwarsa, dan belum memiliki penawaran aktif; pilihan lokasi milik pengguna; validasi deskripsi setelah spasi tepi dibuang; makanan tidak dapat diganti saat edit. | [forms.py](forms.py) |
| CRUD dan status | Tambah, daftar/detail, edit, hapus, serta tandai sudah diambil. Publikasi mengubah status menjadi `OFFERED`; penyelesaian menonaktifkan penawaran dan mengubah makanan menjadi `CONSUMED`. Menghapus penawaran aktif mengembalikan status `OFFERED` ke `STORED`. | [views.py](views.py), [urls.py](urls.py) |
| Pembatasan akses | Login diperlukan; perubahan dibatasi berdasarkan kepemilikan di server. Penawaran yang tidak tersedia disembunyikan dari pengguna lain. Perubahan data menggunakan transaksi; penguncian data dan beberapa pembatasan request disesuaikan lagi saat integrasi kelompok. | [views.py](views.py) |
| Filter | Pencarian nama makanan/area, chip kategori berdasarkan pilihan FoodItem, tab Semua Penawaran/Penawaran Saya, radius 1/2/5/10 km atau semua area | [services.py](services.py), [list.html](../templates/SharedPost/list.html) |
| Lokasi dan jarak | Radius memakai lokasi bawaan milik akun. Jika lokasi belum tersedia, radius dan urutan terdekat dinonaktifkan. Jarak dihitung ke koordinat publik yang dibulatkan, konsisten dengan pin peta. | [services.py](services.py) |
| HTMX | Form tambah/edit dan daftar penawaran diperbarui melalui partial HTML. Event `postCreated`/`postUpdated` memuat ulang daftar; hapus/selesai mengembalikan daftar terbaru langsung. Pencarian memakai debounce 350 ms. Tersedia alur halaman penuh untuk request biasa. | [list.html](../templates/SharedPost/list.html), [partials](../templates/SharedPost/partials/), [sharedpost-ui.js](../static/js/sharedpost-ui.js) |
| Daftar bertahap | Enam penawaran pada tahap awal; tombol Lihat lebih banyak menampilkan hasil kumulatif tanpa duplikasi. Filter dipertahankan, perubahan filter mereset halaman, dan nomor halaman/jumlah hasil disinkronkan melalui HTMX. | [services.py](services.py), [post_list.html](../templates/SharedPost/partials/post_list.html) |
| Tampilan | Integrasi dengan base template kelompok, navigasi, ikon lokasi SVG, keadaan hover/fokus, rasio foto 2:1, placeholder foto, dan grid responsif satu/dua/tiga kolom sesuai lebar layar. Tailwind memakai prefix `sp` dan selector terbatas pada halaman SharedPost. | [base.html](../templates/SharedPost/base.html), [sumber Tailwind](../assets/css/sharedpost.tailwind.css), [hasil CSS](../static/css/sharedpost.css) |
| Gambar | Normalisasi beberapa format tautan Google Drive menjadi URL thumbnail dan penanganan kegagalan foto pada halaman SharedPost. Akses gambar eksternal tetap bergantung pada pemilik berkas dan penyedia layanan. | [services.py](services.py), [sharedpost-ui.js](../static/js/sharedpost-ui.js) |
| Detail, kontak, dan klaim | Detail memuat area, tanggal, petunjuk pengambilan, kontak donor, dan tombol Lihat lokasi. Tombol Klaim pada kartu membuka detail; tombol tersebut belum merupakan reservasi dan tidak otomatis mengubah pemilik/status makanan. | [detail.html](../templates/SharedPost/detail.html), [post_list.html](../templates/SharedPost/partials/post_list.html) |
| Data untuk integrasi peta | Service SharedPost menyediakan judul, deskripsi, gambar, nama area, koordinat publik yang dibulatkan, jarak opsional, dan URL detail penawaran. Halaman detail menyediakan tautan ke lokasi penawaran. | [services.py](services.py), [views.py](views.py), [detail.html](../templates/SharedPost/detail.html) |
| Pengujian dan panduan | Tes backend, service, filter, migrasi, integrasi peta, dan browser; panduan build CSS dan menjalankan tes. | [TESTING.md](TESTING.md), [STYLING.md](STYLING.md), berkas `test*.py` dalam folder ini |

### Penggunaan data dari modul kelompok

Modul saya memakai FoodItem untuk data makanan, Location untuk lokasi pengambilan, serta profil pengguna untuk lokasi bawaan dan kontak donor. Saya mencatatnya sebagai dependensi dan integrasi SharedPost. Implementasi internal modul-modul tersebut tetap merupakan bagian pekerjaan kelompok.

Beberapa penyesuaian SharedPost masuk melalui commit integrasi kelompok `10ab787`, antara lain relasi lokasi menjadi `RESTRICT`, penguncian data, pembatasan request, kontak donor, migrasi, dan tes.

Commit pembaruan SharedPost yang menjadi salah satu acuan dokumen ini:

- `3b68c1d` — `feat: improve SharedPost filters cards and location links`.

## 3. Revisi manual yang saya kerjakan

Selama mencoba SharedPost, saya menemukan beberapa masalah pada hasil draf awal dan langsung menindaklanjutinya dengan menulis kode perbaikan secara manual.

| Masalah awal | Perbaikan manual yang saya lakukan |
| --- | --- |
| Tombol Lihat detail belum memiliki umpan balik hover yang jelas. | Saya menulis dan menyesuaikan class CSS/Tailwind untuk state hover dan fokus agar interaksinya lebih terlihat. |
| Tombol kembali tampak kurang proporsional. | Saya mengatur ulang komposisi ikon, teks, dan margin pada tautan kembali di template HTML. |
| Gambar makanan dari tautan berbagi Google Drive tidak muncul. | Saya menambahkan logika normalisasi URL Drive di file `services.py` dan membuat penanganan fallback (`onerror`) di JavaScript untuk kasus gagal muat. |
| Foto pada kartu mengecil dan ikon lokasi kurang jelas. | Saya menerapkan aturan rasio aspek 2:1 pada class gambar, mengganti ikon menjadi format SVG, dan merapikan tata letak grid pada kartu. |
| Pilihan kategori tidak sesuai dengan kategori FoodItem. | Saya mengubah logika query di backend agar nilai kategori dinamis mengikuti data model FoodItem |
| Tampilan filter belum sesuai referensi desain. | Saya merombak layout filter radius dan kategori, menghubungkan logika radius dengan lokasi bawaan pengguna, dan menyesuaikan navigasi tombol Klaim. |
| Filter pernah tampil memanjang dengan radio besar dan ikon terpisah. | Saya melakukan debugging pada cache CSS, memperbaiki versi aset di template, dan membangun ulang file CSS agar tampilannya kembali rapi. |
| Detail makanan belum menyediakan tombol menuju lokasi. | Saya memodifikasi view context dan menambahkan elemen tombol tautan di template detail untuk mengarah ke lokasi penawaran. |

Selain penyesuaian visual, saya juga menemukan bug logika saat melakukan tes browser di mana parameter halaman lama ikut terbawa saat menekan tombol Lihat lebih banyak (pagination). Saya secara manual memperbaikinya dengan menambahkan atribut `hx-include="unset"`, sehingga filter dan nomor halaman selalu tersinkronisasi murni dari URL tautan.

## 4. Pengujian yang dilakukan dan batas buktinya

### Cakupan tes

- **Backend:** kepemilikan makanan/lokasi, login, validasi deskripsi, satu penawaran aktif per makanan, perubahan status, rollback transaksi, CSRF, penolakan perubahan lewat GET, dan escaping HTML pada deskripsi.
- **Service/filter:** normalisasi Google Drive, koordinat dan jarak publik, lokasi bawaan milik akun, kombinasi pencarian/kategori/kepemilikan, radius, sorting, pagination, dan parameter tidak valid.
- **Browser:** tambah/edit/hapus/selesai melalui HTMX, pembatalan konfirmasi, validasi, filter, Klaim menuju detail/kontak, pagination tanpa reload/duplikasi, menu mobile, dan tata letak pada beberapa ukuran layar.
- **Integrasi SharedPost:** pembentukan data pin dari penawaran, normalisasi URL gambar, koordinat publik, jarak opsional, dan tautan lokasi dari detail. Beberapa tes integrasi mengakses halaman modul terkait sebagai tujuan navigasi.

### Hasil dan batas bukti pengujian

Tes backend, service, filter, tautan lokasi, dan browser SharedPost telah dijalankan dalam sesi pengembangan dengan hasil lulus. Pengujian dilakukan pada beberapa ukuran layar. Kerangka tes awalnya dibantu oleh AI, lalu saya sesuaikan secara manual agar mencakup semua skenario khusus aplikasi.

### Cara mengulang

Ikuti pemasangan dependensi dan browser pada [TESTING.md](TESTING.md). Dari root proyek, setelah virtual environment aktif:

```powershell
python manage.py test SharedPost.tests SharedPost.test_services SharedPost.test_board SharedPost.test_map_link SharedPost.test_migrations
python manage.py test SharedPost.test_browser
```

Untuk membangun ulang CSS setelah perubahan template atau sumber Tailwind:

```powershell
python tools/build_sharedpost_css.py
```

## 5. Keterbatasan implementasi

| Keterbatasan | Dampak dan pemeriksaan yang masih dibutuhkan |
| --- | --- |
| Tes lokal bukan audit keamanan komprehensif. | Login, ownership, CSRF, escaping template, dan `textContent` mengurangi risiko, namun konfigurasi deployment dan penyimpanan secret memerlukan pemeriksaan tersendiri. |
| SQLite tidak membuktikan penguncian baris PostgreSQL. | `transaction.atomic()` dan `select_for_update()` perlu diuji pada database deployment untuk menilai request bersamaan. |
| Titik publik dibulatkan hingga tiga angka desimal. | Ini adalah perkiraan area, bukan anonimitas lokasi absolut. Pengguna perlu tetap memilih informasi yang pantas dibagikan. |
| Jarak dan radius memakai koordinat, bukan rute perjalanan. | Angka adalah perkiraan jarak geografis. Lokasi bawaan bukan posisi GPS real-time pengguna. |
| Filter radius memproses daftar penawaran di Python sebelum pagination. | Data yang jauh lebih besar ke depannya akan memerlukan evaluasi performa dan kemungkinan implementasi query spasial tingkat database. |
| Gambar eksternal bergantung pada penyedia layanan. | URL Drive yang dinormalisasi tidak meng-override pengaturan privasi berkas. |
| Tombol Klaim bersifat navigasi, bukan sistem booking. | Belum ada fitur reservasi eksklusif atau antrean pengambil yang menjamin makanan masih tersedia. |

## 6. Referensi dan pemeliharaan disclosure

- [Panduan pengujian SharedPost](TESTING.md).
- [Panduan styling dan build CSS](STYLING.md).
- [Tes backend](tests.py), [service](test_services.py), [filter dan pagination](test_board.py), [tautan peta](test_map_link.py), [browser](test_browser.py), dan [migrasi](test_migrations.py).

Saya akan memperbarui dokumen ini jika ada fitur, perbaikan manual lanjutan, atau integrasi baru ke dalam SharedPost.