# Map / Location REST API

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET, POST | `/api/locations/` | Daftar lokasi sendiri / simpan lokasi |
| GET, PUT, PATCH, DELETE | `/api/locations/{id}/` | Detail / ubah / hapus lokasi sendiri |
| POST | `/api/locations/{id}/set_default/` | Jadikan lokasi sendiri sebagai lokasi bawaan profil |
| GET | `/api/locations/pins/` | Pin penawaran tersedia beserta jarak dari lokasi bawaan sendiri |

Semua endpoint wajib autentikasi token (`Authorization: Token ...`) atau session
website. Session memerlukan CSRF untuk perubahan. Login token tersedia dari
modul UserProfile. Daftar lokasi memakai pagination DRF 20 per halaman:
`count`, `next`, `previous`, `results`. Pencarian lokasi tersimpan: `?search=beji`.
Pins mengembalikan array langsung seperti payload pin website.

Payload create/PUT:

```json
{"area_name":"Beji","latitude":"-6.361234","longitude":"106.821234"}
```

Owner ditetapkan server. Latitude -90 sampai 90, longitude -180 sampai 180,
maksimal enam angka desimal. PATCH hanya mengubah field yang dikirim.
Lokasi milik orang lain tidak dapat dibaca, diedit, dihapus, atau dijadikan
lokasi bawaan melalui endpoint pribadi (404).

Lokasi yang pernah dipakai penawaran tidak boleh diedit. Lokasi yang masih
direferensikan penawaran tidak boleh dihapus (409), termasuk penawaran nonaktif.
Menghapus lokasi tidak terpakai yang menjadi bawaan akan mengosongkan referensi
profil. Perubahan memakai transaksi dan penguncian lokasi seperti website.

Pin menggunakan `get_map_pins` milik website: hanya penawaran aktif, makanan
OFFERED/belum kedaluwarsa, akun donor aktif, dan lokasi milik donor yang sama.
Koordinat publik dibulatkan tiga digit desimal. Lokasi pribadi yang tidak
dibagikan tidak ditampilkan. Jarak dihitung dari lokasi bawaan akun sendiri
ke titik perkiraan publik; tanpa lokasi bawaan, jarak bernilai null.
API pins dan halaman peta memakai aturan filter dan pembentukan pin yang sama.
Pin tetap memuat `detail_url` halaman SharedPost website; klien Flutter dapat
memakai `id` pin untuk membuka detail API SharedPost.

Endpoint pencarian alamat website `/location/search/?q=...`, layanan Nominatim,
dan halaman Leaflet tetap tersedia dan tidak diubah oleh commit ini.
Endpoint `?search=` di API mencari lokasi tersimpan, bukan pencarian Nominatim.

Respons: create 201, GET/update/action 200, delete 204; validasi 400,
autentikasi 401, CSRF 403, objek di luar akses 404, lokasi digunakan 409.
Respons pribadi menggunakan Cache-Control private/no-store.

Pengujian: `python manage.py test Location.test_api --noinput`.
Tes memakai database sementara dan memeriksa CRUD, ownership, validasi,
lokasi bawaan, relasi penawaran, CSRF, cache, filter ketersediaan pin, serta
kesamaan pin dan jarak dengan halaman peta website.
