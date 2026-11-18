## Alur Implementasi Modul Notification

Modul Notification memberikan pengingat makanan pada **H-7, H-3, dan H-1** sebelum tanggal kedaluwarsa. Pengingat terhubung dengan akun pemilik makanan dan dapat ditampilkan di website serta dikirim melalui email. Perhitungan hari mengikuti zona waktu **Asia/Jakarta**.

### 1. Struktur modul (MVT)

| Bagian | Lokasi | Fungsi |
| --- | --- | --- |
| Model | `notification/models.py` | Menyimpan penerima, makanan, pesan, tahap pengingat, status baca, dan status email. |
| View | `notification/views.py` | Mengatur pembuatan pengingat, tampilan daftar, status baca, dan pengiriman email. |
| URL | `notification/urls.py` | Menghubungkan alamat halaman dan aksi pengguna dengan view. |
| Template | `templates/notification/list.html` | Menampilkan kartu notifikasi dan jumlah pesan belum dibaca. |
| JavaScript | `static/js/notification.js` | Memperbarui status baca melalui AJAX tanpa memuat ulang halaman. |
| CSS | `static/css/notification.css` | Mengatur warna, font, kartu, dan layout responsif. |
| Integrasi | `FoodItem/views.py` | Memicu pemeriksaan dan pengiriman setelah makanan ditambah atau diedit. |

### 2. Fungsi utama

| Fungsi | Tanggung jawab |
| --- | --- |
| `generate_food_reminders()` | Memeriksa makanan aktif dan membuat pengingat yang belum tersedia. |
| `send_pending_reminder_emails()` | Memproses pengingat berstatus `PENDING` atau `FAILED`. |
| `send_reminder_email()` | Memvalidasi ulang satu pengingat, mengirim email, dan mencatat hasilnya. |
| `show_notification()` | Menampilkan notifikasi milik pengguna yang sedang login. |
| `mark_notification_read()` | Mengubah notifikasi milik pengguna menjadi sudah dibaca. |

### 3. Alur penggunaan

#### A. Menambah atau mengedit makanan

1. Pengguna login, mengisi form makanan, lalu menyimpannya.
2. Setelah form valid dan FoodItem tersimpan, view memanggil `generate_food_reminders()` untuk makanan dan pemilik tersebut.
3. Sistem memeriksa status makanan serta selisih tanggal kedaluwarsa dengan tanggal hari ini.
4. Jika tepat H-7, H-3, atau H-1, sistem membuat notifikasi yang belum ada dengan `is_read=False` dan `email_status=PENDING`.
5. View memanggil `send_pending_reminder_emails(food_item=fooditem)` untuk memproses email makanan tersebut.
6. Pengguna diarahkan kembali ke halaman Makananku.

Makanan di luar ketiga tahap tersebut tidak menghasilkan email konfirmasi penambahan makanan.

#### B. Mengirim email pengingat

1. Sistem mengambil pengingat berstatus `PENDING` atau `FAILED`.
2. Setiap pengingat diperiksa ulang: makanan masih ada dan aktif, pemilik sesuai penerima, tanggal kedaluwarsa tidak berubah, tahap masih berlaku hari ini, serta email penerima valid.
3. Jika memenuhi syarat, `send_reminder_email()` mengirim pesan melalui Django `send_mail()` menggunakan konfigurasi SMTP dari environment.
4. Hasil pengiriman disimpan sesuai status berikut.

| Status | Keterangan |
| --- | --- |
| `PENDING` | Menunggu proses pengiriman. |
| `SENT` | Backend email menerima pesan; belum menjadi bukti pesan masuk inbox atau dibaca. |
| `FAILED` | Pengiriman gagal; penyebab disimpan pada `last_email_error`. |
| `SKIPPED` | Pengiriman dilewati karena syarat tidak terpenuhi. |

Email penerima berasal dari akun pemilik makanan. Pesan `SENT` tidak diproses ulang pada alur normal. Pesan `FAILED` dapat dicoba kembali selama masih memenuhi syarat. Kegagalan email tidak menghapus notifikasi di website.

#### C. Membuka halaman notifikasi

1. Pengguna yang sudah login mengakses `/notification/` melalui GET.
2. `show_notification()` memanggil `generate_food_reminders(recipient=request.user)` untuk memeriksa makanan pengguna.
3. View mengambil notifikasi dengan filter `recipient=request.user` dan `select_related("food_item")`.
4. Daftar pesan dan jumlah `is_read=False` dikirim ke template.

Membuka halaman hanya memeriksa dan menampilkan pengingat. Aksi ini tidak mengirim email atau otomatis menandai pesan sebagai sudah dibaca.

#### D. Menandai pesan sudah dibaca

1. Pengguna menekan tombol **Tandai sudah dibaca**.
2. JavaScript mengirim POST ke `/notification/<id>/read/` dengan token CSRF.
3. `mark_notification_read()` memeriksa login dan kepemilikan notifikasi, lalu mengubah `is_read=True`.
4. View mengembalikan JSON berisi hasil perubahan dan jumlah pesan belum dibaca terbaru.
5. JavaScript memperbarui kartu dan jumlah pesan tanpa memuat ulang halaman, atau menampilkan kesalahan jika permintaan gagal.

Status baca hanya berlaku untuk pesan tersebut. Membaca pengingat H-7 tidak membatalkan pengingat H-3/H-1, mengubah status makanan, atau membatalkan pengiriman email.


### 4. Pengujian dan status implementasi

Jalankan pemeriksaan berikut dari folder yang berisi `manage.py`:

```bash
python manage.py check
python manage.py test notification --noinput
```

Tes otomatis menggunakan backend email dalam memori sehingga tidak mengirim email sungguhan.

## AI Disclosure — Modul Notification

Alat bantu : ChatGPT dan Codex dari OpenAI

### Ruang lingkup bantuan

AI digunakan untuk menjelaskan konsep Django MVT, menghasilkan contoh dan sebagian implementasi kode, membantu debugging, serta menyusun pengujian. Bantuan diberikan melalui chat dan perubahan fungsi yang disarankan melalui chatgpt.  pada file proyek pada tahap yang diizinkan.
Bagian yang menggunakan AI : Pembuatan unit testing, melakukan implementasi css atau ui dan ux. Untuk implementasi fungsi di view beberapa terjadi bug dan saya menggunakan ai untuk melakukan fiksasi terhadap bug tersebut. Logika yang mendalam di beberapa fungsi seperti implementasi pengiriman email secara otomatis saya dibantu dengan ai untuk melakukan implementasinya. Sebagian besar template juga saya meminta bantuan ai untuk merapihkannya. Untuk melakukan strukturisasi saya juga di bantu oleh AI dan selebihnya saya mencoba secara mendalam dan melakukan percobaan dengan beberapa contoh di youtube maupun tutorial yang sudah di berikan di modul modul sebelumnya.

###  Alat Bantu Lainnya
- https://www.youtube.com/watch?v=iGPPhzhXBFg
- https://docs.djangoproject.com/en/6.1/topics/email/
-
