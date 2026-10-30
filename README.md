# Projek UTS PBP - B Kelompok 12

## Nama Anggota

1. GHULAM MUHAMMAD IHSAN : 2506656766
2. Muh. Agra Putra Davyza Chaniago : 2506624833
3. ANINDYA RAIHANI HASSAN : 2506553295
4. ILMAN ZIDNI : 2506621951
5. JUSTIN EVAN HALIM SAPUTRA : 2506549386

## Latar Belakang Aplikasi

Hal ini berawal dari concern kita terhadap masyarakat terutama mahasiswa yang tinggal di kos dan sering menyimpan makanan di kulkas bersama. Dikarenakan makanan yang disimpan mahasiswa tergolong banyak dan lamanya waktu penyimpanan yang tidak terdata, terkadang lupa bahwa makanan tersebut sudah kedaluwarsa. Maka dari itu solusi dari kami adalah TitikLapar. TitikLapar, Website ini adalah Personal Food Tracker & Papan Pengumuman Spasial yang dirancang untuk menekan angka food waste. Pengguna dapat mencatat makanan yang mereka beli melalui antarmuka yang simpel dengan memasukkan nama barang dan tanggal pembelian. Jika pengguna tidak mengetahui tanggal kedaluwarsa secara pasti, sistem akan secara otomatis mengestimasi expired date berdasarkan basis data ketahanan pangan bawaan. Ketika sebuah item makanan mendekati masa kedaluwarsa (misalnya H-3), sistem akan mengirimkan notification sebagai pengingat. Di titik ini, pengguna diberikan opsi praktis: mengonsumsinya segera, atau membagikannya secara gratis melalui Papan Berbagi terintegrasi. Di dalam forum ini, makanan yang hampir kedaluwarsa namun masih layak konsumsi dapat diklaim oleh pengguna lain di sekitar mereka, menciptakan ekosistem sirkular yang saling menguntungkan dan ramah lingkungan.

## Daftar Modul

### UserProfile

User berperan sebagai fondasi identitas dan pusat komunikasi antar pengguna di dalam aplikasi. Entitas ini tidak hanya menyimpan data standar seperti nama pengguna dan kata sandi untuk autentikasi, tetapi juga memegang peran krusial dalam sistem transaksi mandiri melalui atribut kontak eksternal, seperti tautan WhatsApp atau ID Line. Selain itu, model ini menyimpan koordinat lokasi bawaan pengguna agar saat fitur peta dibuka, antarmuka dapat langsung memusatkan titik area pada lokasi tersebut tanpa harus selalu menunda pemuatan demi menunggu akses GPS dari peramban.

**Aktivitas pengguna**: mendaftar akun, login, melengkapi nomor kontak, dan mengatur lokasi bawaan.

- **Create**: Registrasi akun
- **Read**: Melihat profil sendiri, melihat kontak donor
- **Update**: Mengubah kontak Whatsapp/Line dan lokasi bawaan
- **Delete**: Menghapus akun beserta profilnya

(Penanggung jawab modul : Ghulam)

### FoodItem

FoodItem bertindak sebagai mesin operasional utama dari fitur pelacak inventori pribadi. Entitas ini bertanggung jawab menyimpan seluruh data operasional makanan yang dimasukkan pengguna, mulai dari nama, kategori, tanggal pembelian, hingga tanggal kedaluwarsa. Model ini menjadi acuan mutlak bagi sistem penjadwal di latar belakang untuk menghitung sisa hari kelayakan konsumsi, serta memiliki penanda status yang secara tegas membedakan apakah suatu makanan masih tersimpan secara privat, sudah habis dikonsumsi, atau sedang ditawarkan ke publik.

**Aktivitas pengguna**: mencatat belanjaan, memantau sisa hari sebelum kedaluwarsa, dan memilih untuk mengonsumsi atau membagikan makanannya.

- **Create**: Menambah makanan (nama otomatis terisi dari Open Food Facts; tanggal kedaluwarsa diestimasi jika tidak diketahui)
- **Read**: Melihat daftar inventori pribadi
- **Update**: Mengedit data makanan
- **Delete**: Menghapus item dari inventori

(Penanggung jawab modul : Zidni)

### SharedPost

SharedPost merepresentasikan penawaran makanan di papan berbagi. Entitas ini memiliki relasi langsung dengan FoodItem, di mana ia mengekstrak informasi barang dan memadukannya dengan Location yang akan dirender menjadi pin lokasi oleh OpenStreetMap dan Leaflet.js. Peran utamanya adalah memastikan tabel inventori pribadi tidak tercampur dengan kueri data publik, sekaligus menyimpan deskripsi pengambilan dari pendonor dan memantau status keaktifan agar pin lokasi dapat disembunyikan seketika saat makanan sudah diambil orang lain.

**Aktivitas pengguna**: pendonor mempublikasikan makanan yang ingin dibagikan; pencari melihat penawaran dan menghubungi pendonor.

- **Create**: Mempublikasikan FoodItem ke papan berbagi beserta deskripsi pengambilan
- **Read**: Melihat daftar penawaran, halaman detail, dan pin di peta
- **Update**: Mengedit deskripsi pengambilan, mengubah status SharedPost menjadi "sudah diambil"
- **Delete**: Menghapus penawaran berbagi makanan

(Penanggung jawab modul : Justin)

### Location

Modul spasial ini secara khusus dirancang untuk berkomunikasi dengan Nominatim API dan Leaflet.js. Modul ini hanya peduli pada tiga hal: Garis Lintang (Latitude), Garis Bujur (Longitude), dan nama area umum (misalnya: "Kecamatan Beji", untuk menjaga privasi alamat persis). Dengan menjadikan lokasi sebagai modul tersendiri (normalisasi data), sistem dapat merender ratusan pin atau marker di atas peta secara ringan dan cepat tanpa perlu menarik seluruh data pengguna atau data makanan yang tidak diperlukan oleh peta. SharedPost menyimpan relasi ke Location sehingga koordinat hanya disimpan di satu lokasi.

**Aktivitas pengguna**: memasukkan alamat saat membuat penawaran dan melihat sebaran makanan di peta.

- **Create**: Menyimpan lokasi baru saat membuat penawaran di papan berbagi
- **Read**: Mengambil titik lokasi untuk dirender di peta
- **Update**: Mengubah koordinat atau nama area di suatu lokasi
- **Delete**: Menghapus lokasi yang tidak lagi dipakai

(Penanggung jawab modul : Anin)

### Notification

Notification memiliki peran sebagai kotak masuk atau riwayat peringatan yang menjembatani sistem otomatisasi di belakang layar dengan pengguna akhir. Peran utamanya adalah menerima dan menyimpan rekaman pesan peringatan yang dihasilkan oleh sistem ketika ada makanan yang mendekati batas waktu kedaluwarsa. Entitas ini merekam tenggat waktu pembuatan pesan dan status keterbacaan, sehingga aplikasi dapat menampilkan atau menyembunyikan indikator visual berwarna pada antarmuka sesuai dengan interaksi pengguna terhadap peringatan tersebut.

**Aktivitas pengguna**: menerima pengingat makanan yang mendekati kedaluwarsa, membukanya, lalu memutuskan untuk mengonsumsi atau mendonasikan makanan tersebut.

- **Create**: Dibuat otomatis oleh sistem saat makanan mendekati kedaluwarsa (misal H-3)
- **Read**: Melihat kotak masuk notifikasi dan indikator belum dibaca
- **Update**: Menandai notifikasi sebagai sudah dibaca
- **Delete**: Menghapus notifikasi dari kotak masuk.

(Penanggung jawab modul : Agra)

## Sumber/dokumentasi Public API

1. _OpenStreetMap (OSM) & Leaflet.js:_ Kombinasi layanan data peta dan library antarmuka. Digunakan untuk menampilkan peta interaktif dan meletakkan titik lokasi makanan di perangkat pengguna.
   Dokumentasi: https://leafletjs.com/reference.html
2. _Nominatim API:_ Layanan geocoding bawaan dari OpenStreetMap. Digunakan untuk mengubah teks alamat yang diinput pengguna menjadi koordinat spasial (Latitude/Longitude) agar bisa dirender ke dalam peta.
   Dokumentasi: https://nominatim.org/release-docs/latest/api/Overview/
3. _Open Food Facts API:_ Basis data produk makanan global. Digunakan pada modul input inventori agar sistem bisa melakukan pengisian otomatis nama dan standar ketahanan makanan saat pengguna mengetikkan nama barang.
   Dokumentasi: https://openfoodfacts.github.io/openfoodfacts-server/api/

## Peran Pengguna

**Guest (belum login)**: Melihat landing page
**User (setelah login)**: Mengelola inventori makanan sendiri, mempublikasikan dan mengelola penawaran di papan berbagi, melihat kontak donor, dan mengelola profil dan notifikasi sendiri.
**Admin**: Memoderasi pengumuman yang tidak pantas dan mengelola data pengguna

**Alur singkat**: Jika pengguna merasa tidak sanggup menghabiskan makanan tersebut, mereka dapat memublikasikannya ke Papan Berbagi. Pengguna lain dapat membuka antarmuka peta interaktif untuk melihat sebaran makanan gratis di sekitar mereka. Ketika sebuah titik (pin) di peta ditekan, aplikasi akan langsung membuka halaman detail pengumuman tersebut. Dari sana, pencari makanan dapat menekan tombol kontak yang langsung mengarahkan mereka ke aplikasi pesan singkat (seperti WhatsApp) milik pendonor. Seluruh proses transaksi dan pengambilan dilakukan secara mandiri (peer-to-peer).

## Tautan deployment PWS

https://justin-evan-titiklapar.pws.cs.ui.ac.id/

## Tautan Figma

https://www.figma.com/design/r3aIEwY6EmWnxDocq8Rrl3/Projek-PBP-B12?node-id=0-1&t=RJOL7DroOzRv7Kqf-1

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