# UserProfile REST API

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| POST | `/api/auth/register/` | Registrasi akun dan profil |
| POST | `/api/auth/login/` | Login dan ambil token |
| POST | `/api/auth/logout/` | Cabut token dan akhiri sesi |
| GET | `/api/profile/` | Profil sendiri |
| PUT, PATCH | `/api/profile/` | Ubah email, kontak, lokasi bawaan |
| DELETE | `/api/profile/` | Hapus akun sendiri dengan password dan konfirmasi |
| GET | `/api/contacts/{user_id}/` | Kontak donor aktif tanpa email atau lokasi pribadi |

Registrasi menggunakan RegistrationForm website, termasuk validasi dan hashing
password. Payload: `username`, `email`, `password1`, `password2`.
Login menerima `username`, `password`, dan merespons `token`, `user_id`, `username`.
Kirim token melalui header `Authorization: Token <token>`.
Endpoint selain login/registrasi wajib autentikasi. Session website didukung;
perubahan dengan session memerlukan CSRF. Login/registrasi dibatasi 20 request
per menit per IP melalui cache Django. Token harus dikirim lewat HTTPS di produksi.

Profil menerima `email`, `whatsapp_number`, `line_id`, `default_location`.
Lokasi bawaan wajib milik sendiri; gunakan null untuk mengosongkannya.
Nomor WhatsApp berupa 8-15 digit tanpa spasi atau tanda +, boleh kosong.
Username, password, pemilik profil dan hak admin tidak dapat diubah lewat profil.
PATCH mempertahankan field yang tidak dikirim. PUT memerlukan email.

Hapus akun: `{"password":"kata-sandi-saat-ini","confirm":true}`.
Password diverifikasi terhadap akun yang dikunci dalam transaksi; data terkait
mengikuti aturan relasi database website. Bila masih ada relasi yang menghalangi,
API merespons 409 dan transaksi dibatalkan. Penghapusan sukses mencabut token.
Logout POST tanpa body mencabut token akun dan mengakhiri sesi permintaan.

Respons: registrasi 201, login/profil/kontak/update 200, logout/delete 204;
validasi 400, autentikasi 401, CSRF 403, donor tidak ditemukan/nonaktif 404,
konflik penghapusan 409, rate limit 429. Respons pribadi diberi no-store/private.

Pengujian: `python manage.py test userprofile.test_api --noinput`.
Menggunakan database tes terpisah; mencakup registrasi, login/logout, token,
ownership profil/lokasi, larangan perubahan hak akses, privasi kontak, validasi,
hapus akun, CSRF, rate limit, dan pembacaan perubahan melalui website.
