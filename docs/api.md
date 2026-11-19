# API Django REST Framework - TitikLapar

API lokal untuk Checkpoint 1 proyek mobile. Lima modul menggunakan serializer
dan view/viewset DRF, terhubung ke model/database yang sama dengan situs Django.
Endpoint HTML dan JSON lama tetap tersedia untuk situs web.

## Menjalankan dan menguji

Jalankan dari direktori proyek di PowerShell:

```powershell
.\env\Scripts\python.exe -m pip install -r requirements.txt
.\env\Scripts\python.exe manage.py migrate
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py test TitikLapar.test_api --noinput
.\env\Scripts\python.exe manage.py runserver
```

Base URL lokal: `http://127.0.0.1:8000/api/`. Selalu gunakan trailing slash.
DRF browsable API tersedia di URL tersebut setelah login web. Login API
mengembalikan token, bukan cookie sesi. Flutter native memakai token ini.

Semua endpoint selain register dan login membutuhkan autentikasi:

```http
Authorization: Token TOKEN_DARI_LOGIN
Content-Type: application/json
Accept: application/json
```

SessionAuthentication juga didukung untuk browsable API; mutasi memakai sesi
tetap wajib menyertakan CSRF. TokenAuthentication tidak memerlukan CSRF.
Gunakan HTTPS ketika menghubungkan aplikasi ke PWS. Token dianggap rahasia,
disimpan aman oleh aplikasi, dan dihapus saat logout. Flutter Web lintas origin
memerlukan konfigurasi CORS tersendiri sesuai origin frontend; belum ditambahkan.

## Daftar endpoint

`{id}` adalah ID numerik objek, `{user_id}` adalah ID akun donor.

| Modul | Method | Endpoint | Fungsi |
| --- | --- | --- | --- |
| Indeks | GET | `/api/` | Tautan koleksi API |
| Akun | POST | `/api/auth/register/` | Daftar akun dan profil |
| Akun | POST | `/api/auth/login/` | Login dan ambil token |
| Akun | POST | `/api/auth/logout/` | Cabut token dan akhiri sesi |
| Profil | GET | `/api/profile/` | Profil akun sendiri |
| Profil | PUT, PATCH | `/api/profile/` | Ubah email, WhatsApp, Line, lokasi bawaan |
| Profil | DELETE | `/api/profile/` | Hapus akun sendiri dengan password dan konfirmasi |
| Profil | GET | `/api/contacts/{user_id}/` | Kontak donor, tanpa email/lokasi pribadi |
| Makanan | GET, POST | `/api/foods/` | Daftar makanan sendiri / buat makanan |
| Makanan | GET, PUT, PATCH, DELETE | `/api/foods/{id}/` | Detail / ubah / hapus makanan sendiri |
| Makanan | POST | `/api/foods/{id}/status/` | Ubah status makanan sendiri |
| Lokasi | GET, POST | `/api/locations/` | Daftar lokasi sendiri / buat lokasi |
| Lokasi | GET, PUT, PATCH, DELETE | `/api/locations/{id}/` | Detail / ubah / hapus lokasi sendiri |
| Lokasi | POST | `/api/locations/{id}/set_default/` | Jadikan lokasi sendiri sebagai bawaan profil |
| Lokasi | GET | `/api/locations/pins/` | Pin penawaran aktif dengan koordinat perkiraan |
| Berbagi | GET, POST | `/api/posts/` | Daftar penawaran tersedia / buat penawaran |
| Berbagi | GET, PUT, PATCH, DELETE | `/api/posts/{id}/` | Detail / ubah / hapus penawaran |
| Berbagi | POST | `/api/posts/{id}/complete/` | Tandai diambil; makanan menjadi CONSUMED |
| Notifikasi | GET | `/api/notifications/` | Daftar pengingat sendiri |
| Notifikasi | GET | `/api/notifications/{id}/` | Detail pengingat sendiri |
| Notifikasi | POST | `/api/notifications/{id}/read/` | Tandai sudah dibaca |
| Notifikasi | GET | `/api/notifications/unread-count/` | Jumlah belum dibaca |
| Notifikasi | POST | `/api/notifications/refresh/` | Buat pengingat H-7/H-3/H-1 milik sendiri |

Daftar koleksi memakai pagination DRF:

```json
{"count": 1, "next": null, "previous": null, "results": [{"id": 1}]}
```

Gunakan `?page=2`. `/api/locations/pins/` mengembalikan array langsung;
endpoint profil, detail, dan action mengembalikan objek JSON.

## Contoh payload JSON

Register (`201`):

```json
{"username":"pengguna_baru","email":"saya@example.com","password1":"PasswordKuatUnik!273","password2":"PasswordKuatUnik!273"}
```

Login (`200`):

```json
{"username":"pengguna_baru","password":"PasswordKuatUnik!273"}
```

Respons login: `{"token":"...","user_id":1,"username":"pengguna_baru"}`.
Login/register dibatasi 20 permintaan per menit per IP melalui cache Django.

Buat makanan (`201`; ID owner ditetapkan server, status awal `STORED`):

```json
{"name":"Apel","category":"FRUIT","purchase_date":"2026-11-18","expiration_date":"2026-11-25","image_url":""}
```

Tanggal yang tidak disertakan saat create memakai hari ini. Tanggal kedaluwarsa
tidak boleh lebih awal daripada tanggal beli. Nilai kategori: `FRUIT`,
`VEGETABLE`, `MEAT`, `SEAFOOD`, `DAIRY`, `GRAIN`, `BEVERAGE`, `SNACK`, `OTHER`.
URL gambar wajib HTTP/HTTPS bila diisi. `owner`, `status`, timestamp dan field
turunan hanya dibaca. Ubah status melalui endpoint khusus:

```json
{"status":"CONSUMED"}
```

Status valid: `STORED`, `CONSUMED`, `OFFERED`. `OFFERED` memerlukan penawaran
aktif dan makanan belum kedaluwarsa. Membuat penawaran merupakan cara normal
membagikan makanan. Status STORED/CONSUMED menonaktifkan penawaran aktifnya.

Buat lokasi (`201`):

```json
{"area_name":"Beji","latitude":"-6.361234","longitude":"106.821234"}
```

Latitude -90 s.d. 90 dan longitude -180 s.d. 180, maksimal 6 digit desimal.
Lokasi yang pernah dipakai penawaran tidak dapat diubah; lokasi yang masih
direferensikan penawaran tidak dapat dihapus (`409`). Tambahkan lokasi baru.
Pin publik menggunakan pembulatan 3 digit desimal seperti peta situs web;
lokasi pribadi yang tidak dibagikan tidak muncul di pin.

Buat penawaran (`201`; gunakan ID hasil create makanan dan lokasi):

```json
{"food_item":1,"location":1,"description":"Ambil di gerbang utama sebelum sore."}
```

Makanan dan lokasi wajib milik akun sendiri; makanan harus `STORED`, belum
kedaluwarsa, dan belum memiliki penawaran aktif. Description minimal 10 karakter.
Create otomatis mengubah status makanan ke `OFFERED`. Edit tidak dapat mengganti
makanan. Delete penawaran aktif mengembalikan makanan ke `STORED`; complete
mengubahnya menjadi `CONSUMED`. Penawaran tidak aktif tidak bisa diedit/diselesaikan
ulang. Semua mutasi penawaran berbagi kuota dengan situs web (default 20 per menit
per akun); respons `429` menyertakan `Retry-After`.

Ubah profil (`PATCH`, `200`):

```json
{"email":"baru@example.com","whatsapp_number":"628123456789","line_id":"id-line","default_location":1}
```

Lokasi bawaan harus milik sendiri, atau `null` untuk mengosongkannya.
WhatsApp berupa 8-15 angka tanpa spasi/tanda `+`, boleh kosong.

Hapus akun (`DELETE`, `204`):

```json
{"password":"PasswordKuatUnik!273","confirm":true}
```

Action `complete/`, `set_default/`, `read/`, `refresh/`, dan logout menerima
POST tanpa body. Notifikasi dibuat sistem, bukan POST notifikasi bebas.
Membuka daftar notifikasi dan action refresh membuat pengingat milik sendiri
tanpa mengirim email. Penyimpanan makanan melalui API menggunakan alur web:
setelah transaksi berhasil, sistem membuat dan memproses email pengingat untuk
makanan itu. Perintah `send_food_reminders` tetap tersedia untuk pekerjaan terjadwal.
Memperpanjang tanggal makanan yang sudah kedaluwarsa menutup penawaran lamanya;
penawaran tidak diaktifkan ulang otomatis.
DELETE notifikasi per item tidak disediakan, sesuai perilaku modul situs web.

## Pencarian, filter, dan urutan

- Makanan: `?search=apel&ordering=expiration_date` atau `ordering=-expiration_date`.
  Field urutan: `expiration_date`, `name`, `created_at`.
- Lokasi pribadi: `?search=beji`.
- Papan berbagi: `?search=apel`, `?category=FRUIT`, `?mine=1`,
  `?ordering=food_item__expiration_date` atau `?ordering=-created_at`.
- Daftar papan hanya memuat penawaran aktif, makanan OFFERED/belum kedaluwarsa,
  dan pemilik aktif. Detail penawaran tidak tersedia hanya bisa dilihat pemilik.

## Status dan pengujian

Respons normal: GET/update/action `200`, create `201`, delete/logout `204` tanpa
body. Error: `400` validasi, `401` tanpa token/token salah/login salah, `403`
CSRF sesi tidak valid, `404` objek hilang atau di luar hak akses, `405` metode
tidak didukung, `409` konflik status/lokasi, `429` kuota request habis.

`TitikLapar/test_api.py` mencakup autentikasi token, CRUD, validasi, isolasi
pemilik, sinkronisasi status makanan/penawaran, privasi pin/kontak,
pengingat/read count, CSRF sesi, logout/pencabutan token, serta rate limit.
Pengujian menggunakan database test terpisah dan tidak mengirim email.

Ini mencakup sisi Django Checkpoint 1. Repositori Flutter, halaman/navigasi mobile,
README Flutter, desain, APK, dan deployment PWS dikerjakan terpisah.
