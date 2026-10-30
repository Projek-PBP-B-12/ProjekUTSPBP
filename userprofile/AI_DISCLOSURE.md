# AI Disclosure — UserProfile dan Integrasi Antar Modul

**Alat AI:** OpenAI Codex
**Tanggal penyusunan:** 30 Oktober 2026

## Pernyataan penggunaan AI

Saya menggunakan OpenAI Codex dalam pengembangan modul UserProfile pada aplikasi TitikLapar. Bantuan AI meliputi penjelasan konsep Django, penyusunan dan perbaikan kode, penelusuran error, penulisan pengujian otomatis, serta integrasi UserProfile dengan modul kelompok. Dalam tahap integrasi, AI juga membaca dan mengubah berkas proyek secara langsung serta menjalankan pengujian melalui terminal.

Dokumen ini mencakup pekerjaan UserProfile dan penyesuaian yang diperlukan untuk menghubungkannya dengan modul lain. Implementasi keseluruhan modul FoodItem, SharedPost, Location, dan Notification tetap merupakan pekerjaan kelompok dengan penanggung jawab masing-masing.

## Cakupan bantuan AI

| Bagian                                  | Bantuan yang digunakan                                                                                                                                                                                                                                                                                                          |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model dan autentikasi                   | Membantu menghubungkan `UserProfile` dengan `User` bawaan Django, menjelaskan `Meta`, serta menyusun dan memeriksa registrasi, login, logout, validasi formulir, dan penggunaan hashing kata sandi bawaan Django.                                                                                                               |
| CRUD profil                             | Membantu implementasi halaman profil sendiri, perubahan WhatsApp/Line, halaman kontak donor, dan penghapusan akun dengan pemeriksaan kata sandi serta konfirmasi.                                                                                                                                                               |
| Email pengguna                          | Membantu menambahkan email wajib pada registrasi dan edit profil melalui `User.email`. Email tetap tersimpan pada model akun bawaan, bukan kolom baru yang terpisah di `UserProfile`. Perubahan email dan profil disimpan dalam satu transaksi.                                                                                 |
| Integrasi Location                      | Membantu mengganti koordinat yang sebelumnya tersimpan langsung pada profil menjadi relasi `default_location`. Pilihan dibatasi pada lokasi milik pengguna. Satu pengguna dapat menyimpan beberapa lokasi, sedangkan profil menunjuk satu lokasi bawaan untuk pusat peta. Migrasi memindahkan koordinat lama ke model Location. |
| Integrasi SharedPost                    | Membantu menghubungkan penawaran dengan kontak donor dari UserProfile. Halaman kontak menampilkan WhatsApp/Line tanpa menampilkan email atau koordinat pribadi. Lokasi pengambilan penawaran tetap terpisah dari pilihan lokasi bawaan profil.                                                                                  |
| Integrasi FoodItem dan penghapusan akun | Membantu memeriksa hubungan kepemilikan serta penghapusan akun beserta profil, makanan, penawaran, lokasi, dan notifikasi terkait. Penyesuaian relasi dan transaksi menjaga agar penghapusan tidak ikut menghapus data milik pengguna lain.                                                                                     |
| Integrasi Notification                  | Membantu menghubungkan alamat pada `User.email` dengan pengingat kedaluwarsa makanan dan menguji penggunaan alamat terbaru setelah profil diperbarui.                                                                                                                                                                           |
| Integrasi kode dan pengujian            | Membantu membandingkan salinan kode terbaru, menyelesaikan benturan perubahan, mempertahankan migrasi yang sudah ada, serta menulis dan menjalankan pengujian autentikasi, profil, migrasi, dan hubungan antar modul.                                                                                                           |

Berkas utama UserProfile meliputi [models.py](models.py), [forms.py](forms.py), [views.py](views.py), [urls.py](urls.py), template pada folder `templates/userprofile/`, dan [migrasi lokasi bawaan](migrations/0002_saved_default_location.py).

## Peran saya selama pengembangan

Saya memberikan spesifikasi modul, meminta pengerjaan bertahap, menyampaikan hasil percobaan dan pesan error, serta meminta penjelasan agar dapat memahami hubungan model, formulir, view, dan migrasi. Saya juga menentukan kebutuhan tambahan berupa email, beberapa lokasi tersimpan, dan lokasi bawaan, lalu memberikan salinan kode kelompok yang menjadi acuan integrasi.

Contoh arahan yang saya berikan adalah permintaan untuk memeriksa kode UserProfile, menjelaskan perintah migrasi dan pengujian, menambahkan email untuk notifikasi, serta mengintegrasikan perubahan dengan salinan production terbaru. Peninjauan akhir, pemahaman kode, keputusan commit/push, dan penyerahan tugas tetap menjadi tanggung jawab saya.

## Pengujian dan batas validasi

AI membantu menyusun dan menjalankan pengujian selama pengembangan. Berkas pengujian UserProfile mencakup:

- Registrasi, login/logout, validasi input, CSRF, dan pembatasan akses: [tests.py](tests.py), [test_auth.py](test_auth.py).
- Perubahan profil, validasi kontak, pilihan lokasi milik sendiri, dan privasi kontak donor: [test_profile.py](test_profile.py).
- Konfirmasi penghapusan akun dan penolakan permintaan yang tidak valid: [test_delete.py](test_delete.py).
- Penggunaan email oleh notifikasi, rollback perubahan profil/email, serta penghapusan data terkait lintas modul: [test_integration.py](test_integration.py).
- Pemindahan koordinat lama dan pemulihan saat rollback migrasi: [test_migrations.py](test_migrations.py).

Pengujian email menggunakan backend memori atau mock. Hasil tersebut tidak membuktikan pengiriman ke inbox melalui SMTP produksi. Konfigurasi SMTP dan penjadwalan pengingat pada server tetap perlu disiapkan dan diperiksa. Validasi format email juga belum merupakan verifikasi kepemilikan alamat email.

Pengujian otomatis merupakan bagian dari verifikasi, bukan jaminan bahwa seluruh kemungkinan kesalahan atau masalah keamanan telah ditemukan.
