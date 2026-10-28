# Keamanan SharedPost

SharedPost memeriksa login, kepemilikan makanan/lokasi, CSRF, metode request, dan validasi form di server. Rate limiting merupakan lapisan tambahan untuk membatasi percobaan perubahan berulang dari akun yang sama.

## Batas perubahan per akun

Decorator khusus `limit_sharedpost_writes` pada [decorators.py](decorators.py) dipasang pada view tambah, edit, hapus, dan tandai sudah diambil. Batas awal adalah **20 percobaan POST dalam 60 detik**, gabungan keempat aksi dan seluruh ID penawaran untuk satu akun.

- Percobaan POST yang sudah lolos pemeriksaan login, CSRF, dan metode request memakai satu slot, termasuk form tidak valid atau perubahan yang kemudian gagal.
- Request yang ditolak karena kuota habis tidak menjalankan view dan tidak mengubah makanan atau penawaran.
- GET untuk membaca daftar/detail dan membuka form tetap tersedia.
- Logout, login ulang, atau mengganti sesi/ID penawaran tidak menghapus kuota. Akun berbeda mempunyai kuota sendiri.
- Kunci kuota memakai ID akun terautentikasi, bukan alamat IP atau header `X-Forwarded-For` yang dikirim klien.

Jendela waktu dimulai pada percobaan pertama dan direset setelah 60 detik. Ini merupakan **fixed window**, sehingga percobaan dapat berkumpul di dekat pergantian jendela; mekanisme ini tidak menjamin jarak minimum antar request.

## Penyimpanan dan konkurensi

[models.py](models.py) menyediakan model operasional `SharedPostWriteQuota`, satu baris per akun. Semua worker yang terhubung ke database yang sama memakai penghitung yang sama. Penambahan/reset kuota menggunakan satu `UPDATE` bersyarat dengan `F()` dan `Case`, sehingga keputusan menerima dan menambah penghitung dilakukan dalam pernyataan database yang sama, bukan dengan membaca lalu menyimpan angka di Python.

Pilihan ini menghindari kuota terpisah pada cache memori setiap proses. Django menjelaskan bahwa [local-memory cache bersifat per proses](https://docs.djangoproject.com/en/5.2/topics/cache/#local-memory-caching), dan [ekspresi F menghindari race condition pembaruan penghitung](https://docs.djangoproject.com/en/5.2/ref/models/expressions/#avoiding-race-conditions-using-f).

Tes lokal SQLite belum membuktikan perilaku seluruh request paralel di PostgreSQL. Uji beban/konkurensi tetap diperlukan pada konfigurasi deployment. Penghitung berada di luar blok transaksi perubahan penawaran; dengan konfigurasi transaksi request default proyek, rollback perubahan inventori tidak mengembalikan slot percobaan yang sudah digunakan.

## Respons saat batas terlampaui

Server mengembalikan **HTTP 429 Too Many Requests**, header `Retry-After` berisi sisa detik, dan respons yang tidak boleh di-cache. Pemakaian 429 untuk penolakan akibat rate limiting sesuai [panduan OWASP](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html#http-return-code).

- Request biasa menampilkan halaman penjelasan dan tautan kembali ke papan.
- HTMX menampilkan pesan waktu tunggu tanpa mengganti form, sehingga input tambah/edit tetap tersedia.
- Pada aksi optimistic Hapus/Selesai, kartu dan jumlah dipulihkan. Pengguna tetap dapat memilih Periksa ulang daftar, yang mengirim pembacaan GET.

Mengaktifkan kembali tombol di browser tidak melewati pemeriksaan di server.

## Konfigurasi dan migrasi

Nilai bawaan tersedia tanpa perubahan settings. Jika kebutuhannya berbeda, tetapkan bilangan bulat positif di settings Django:

```python
SHAREDPOST_WRITE_LIMIT = 20
SHAREDPOST_WRITE_WINDOW_SECONDS = 60
```

Konfigurasi nol, negatif, atau tipe yang tidak sesuai ditolak. Tidak ada fallback yang mematikan pembatasan saat database bermasalah; kegagalan akses database harus diselesaikan sebelum operasi perubahan dilanjutkan.

Migrasi yang perlu disertakan saat deployment adalah `SharedPost/0004_sharedpost_write_quota.py`. Dari root proyek:

```powershell
python manage.py migrate
python manage.py test SharedPost
```

## Batas perlindungan

Rate limiting ini membatasi percobaan perubahan per akun. Mekanisme ini tidak menggantikan authorization, proteksi login, pengamanan secret, HTTPS, atau pembatasan trafik di reverse proxy. Akun berbeda mempunyai kuota masing-masing, dan request yang ditolak tetap mencapai aplikasi/database. Karena itu, fitur ini tidak diklaim sebagai perlindungan menyeluruh terhadap DDoS atau serangan dari banyak akun.

Tes khusus ada pada [test_rate_limit.py](test_rate_limit.py) dan skenario browser di [test_browser.py](test_browser.py). Untuk mendemonstrasikan batas rendah, gunakan `override_settings` pada tes; tidak perlu melakukan spam pada data aplikasi yang sebenarnya.
