# SharedPost REST API

Author modul: Justin Evan Halim Saputra.

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET, POST | `/api/posts/` | Daftar penawaran tersedia / buat penawaran |
| GET, PUT, PATCH, DELETE | `/api/posts/{id}/` | Detail / ubah / hapus |
| POST | `/api/posts/{id}/complete/` | Tandai diambil |

Semua endpoint memerlukan autentikasi. Session website tetap didukung, dengan
CSRF untuk perubahan. Klien mobile dapat memakai header `Authorization: Token ...`.
Login token/registrasi mobile merupakan bagian modul userprofile dan commit terpisah.
Untuk pengujian commit ini, login lewat `/accounts/login/` lalu buka `/api/posts/`
di browser; token pengembangan juga bisa dibuat melalui admin/shell Django.

Payload create:

```json
{"food_item":1,"location":1,"description":"Ambil di gerbang utama sebelum sore."}
```

Makanan wajib milik sendiri, STORED, belum kedaluwarsa, tanpa penawaran aktif.
Lokasi wajib milik sendiri. Deskripsi minimal 10 karakter. Makanan tidak bisa
diganti saat edit. Status/owner/timestamp tidak bisa diisi bebas melalui payload.
Pembuatan mengubah makanan menjadi OFFERED; complete mengubahnya menjadi
CONSUMED dan menutup penawaran. Hapus penawaran aktif mengembalikan makanan
OFFERED menjadi STORED. Seluruhnya menggunakan transaksi dan urutan penguncian
makanan/penawaran yang sama dengan website.

Pengguna lain hanya bisa membaca penawaran tersedia; pemilik bisa membaca
detail penawaran yang sudah ditutup. Semua perubahan dibatasi pemilik.
Kuota tulis web/API memakai penghitung SharedPost yang sama, default 20/menit.
Respons pribadi memakai `Cache-Control: private, no-store`.

Filter: `?mine=1`, `?category=FRUIT`, `?search=apel`.
Urutan: `?ordering=food_item__expiration_date` atau `?ordering=-created_at`.
Daftar menggunakan pagination DRF: `count`, `next`, `previous`, `results`;
20 objek per halaman, halaman berikutnya memakai `?page=2`.

Jalankan dengan Python environment proyek:

```powershell
.\env\Scripts\python.exe -m pip install -r requirements.txt
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe manage.py test SharedPost.test_api --noinput
.\env\Scripts\python.exe manage.py runserver
```

Pengujian SharedPost mandiri mencakup CRUD, ownership, status, validasi,
autentikasi, CSRF, kuota, cache, dan alur web-API dengan database tes terpisah.
