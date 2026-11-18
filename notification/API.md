# Notification REST API

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET | `/api/notifications/` | Daftar notifikasi akun sendiri, sekaligus menghasilkan pengingat yang jatuh tempo |
| GET | `/api/notifications/{id}/` | Detail notifikasi sendiri |
| POST | `/api/notifications/{id}/read/` | Tandai dibaca |
| GET | `/api/notifications/unread-count/` | Jumlah notifikasi belum dibaca |
| POST | `/api/notifications/refresh/` | Buat pengingat H-7/H-3/H-1 milik sendiri tanpa duplikasi |

Wajib login melalui session website atau header `Authorization: Token ...`.
Session tetap memerlukan CSRF untuk POST. Action POST menerima body kosong.
Daftar memakai pagination DRF (`count`, `next`, `previous`, `results`).
Notifikasi hanya dapat dibaca/diperbarui penerimanya; ID akun lain merespons 404.
Field kesalahan pengiriman internal tidak disertakan dalam respons API.

Pembuatan pengingat memakai `generate_food_reminders` yang sama dengan website.
Refresh/daftar tidak mengirim email. Pengiriman tetap memakai alur penyimpanan
makanan dan perintah `send_food_reminders` yang sudah ada. Menandai dibaca
tidak mengubah status pengiriman email atau status makanan. Tidak tersedia
create, edit, atau delete bebas per notifikasi, sesuai aturan modul lama.

Pengujian: `python manage.py test notification.test_api --noinput`.
Tes memakai database sementara dan mencakup isolasi pengguna, autentikasi,
CSRF, privasi respons, pengingat tanpa duplikasi, serta sinkronisasi web/API.
