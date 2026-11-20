# FoodItem REST API

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET, POST | `/api/foods/` | Daftar makanan sendiri / buat makanan |
| GET, PUT, PATCH, DELETE | `/api/foods/{id}/` | Detail / ubah / hapus makanan sendiri |
| POST | `/api/foods/{id}/status/` | Ubah status makanan sendiri |

Wajib token (`Authorization: Token ...`) atau session website. Perubahan memakai
session tetap memerlukan CSRF. Makanan orang lain tidak bisa dibaca atau diubah
melalui inventori pribadi (404). Penawaran publik tersedia lewat API SharedPost.

Payload create/PUT:

```json
{"name":"Apel","category":"FRUIT","purchase_date":"2026-11-19","expiration_date":"2026-11-22","image_url":""}
```

Tanggal kosong/null pada input menjadi hari ini; tanggal yang tidak dikirim saat
create juga menjadi hari ini. PATCH mempertahankan field yang tidak dikirim.
Tanggal kedaluwarsa tidak boleh lebih awal dari tanggal beli. Nama dibersihkan
dari tag HTML, kategori mengikuti pilihan model, foto opsional memakai HTTP/HTTPS.
Owner ditetapkan server; status awal STORED. Field status, owner, timestamp,
days_until_expiration, dan is_expired tidak dapat diisi bebas oleh klien.

Payload status: `{"status":"CONSUMED"}`. Nilai valid: STORED, CONSUMED, OFFERED.
OFFERED memerlukan penawaran aktif dan makanan belum kedaluwarsa; normalnya
makanan dibagikan melalui create SharedPost. STORED/CONSUMED menutup penawaran
aktif. Perubahan tanggal makanan yang sebelumnya atau sesudah edit kedaluwarsa
juga menutup penawaran, dan mengembalikan OFFERED ke STORED. Memperpanjang
tanggal kedaluwarsa tidak otomatis menghidupkan penawaran lama.

Penyimpanan memakai transaksi/penguncian seperti website. Pengingat dijadwalkan
melalui `_schedule_food_reminders` yang sama, hanya setelah transaksi sukses.
Hapus makanan menghapus penawaran terkait; riwayat notifikasi tetap disimpan
dengan referensi food_item dikosongkan.

Daftar: pagination DRF (`count`, `next`, `previous`, `results`), 20 per halaman.
Cari nama dengan `?search=apel`. Urutkan melalui `?ordering=expiration_date`,
`?ordering=-expiration_date`, `?ordering=name`, atau `?ordering=-created_at`.
Filter UI website lama tetap tersedia pada endpoint website; API ini menyediakan
search dan ordering yang dijelaskan di atas. Respons pribadi memakai no-store.

Respons: create 201, baca/update/status 200, delete 204; validasi 400,
autentikasi 401, CSRF 403, data di luar akses 404, konflik status OFFERED 409.
Tidak ada perubahan model atau migrasi baru pada modul ini.

Pengujian: `python manage.py test FoodItem.test_api --noinput`.
Tes memakai database sementara, pengiriman email diganti mock ketika callback
dijalankan. Cakupan: CRUD, ownership, validasi, status lintas SharedPost,
kedaluwarsa, riwayat notifikasi, pengingat setelah commit, CSRF, dan alur web/API.
