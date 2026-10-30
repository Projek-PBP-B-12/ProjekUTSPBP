# Projek UTS PBP - B Kelompok 12

## Nama Anggota

1. GHULAM MUHAMMAD IHSAN : 2506656766
2. Muh. Agra Putra Davyza Chaniago : 2506624833
3. ANINDYA RAIHANI HASSAN : 2506553295
4. ILMAN ZIDNI : 2506621951
5. JUSTIN EVAN HALIM SAPUTRA : 2506549386

## Latar Belakang Aplikasi

Hal ini berawal dari concern kita terhadap masyarakat terutama mahasiswa yang tinggal di kos dan sering menyimpan makanan di kulkas bersama. Dikarenakan makanan yang disimpan mahasiswa tergolong banyak dan lamanya waktu penyimpanan yang tidak terdata, terkadang lupa bahwa makanan tersebut sudah kedaluwarsa. Maka dari itu solusi dari kami adalah TitikLapar. TitikLapar, Website ini adalah Personal Food Tracker & Papan Pengumuman Spasial yang dirancang untuk menekan angka food waste. Pengguna dapat mencatat makanan yang mereka beli melalui antarmuka yang simpel dengan memasukkan nama barang dan tanggal pembelian. Pengguna mengisi tanggal kedaluwarsa, lalu sistem menghitung sisa hari berdasarkan tanggal tersebut. Tanggal pembelian dan kedaluwarsa yang tidak diisi menggunakan tanggal hari ini sebagai nilai bawaan. Ketika sebuah item makanan mendekati masa kedaluwarsa (misalnya H-3), sistem akan mengirimkan notification sebagai pengingat. Di titik ini, pengguna diberikan opsi praktis: mengonsumsinya segera, atau membagikannya secara gratis melalui Papan Berbagi terintegrasi. Di dalam forum ini, makanan yang hampir kedaluwarsa namun masih layak konsumsi dapat diklaim oleh pengguna lain di sekitar mereka, menciptakan ekosistem sirkular yang saling menguntungkan dan ramah lingkungan.

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

FoodItem mengelola inventori makanan pribadi milik pengguna. Data yang disimpan meliputi nama, kategori, tanggal pembelian, tanggal kedaluwarsa, dan URL foto opsional. Sistem menghitung sisa hari menuju kedaluwarsa untuk menampilkan penanda pada inventori dan menjadi acuan pengingat Notification. Status makanan membedakan makanan yang tersimpan (`STORED`), sedang ditawarkan melalui SharedPost (`OFFERED`), atau sudah habis (`CONSUMED`). Tanggal pembelian dan kedaluwarsa bersifat opsional; jika dikosongkan, nilainya menggunakan tanggal hari ini.

**Aktivitas pengguna**: mencatat makanan, mencari dan menyaring inventori, melihat detail serta sisa hari sebelum kedaluwarsa, menandai makanan sudah habis, atau membagikannya melalui SharedPost.

- **Create**: Memasukkan nama dan kategori makanan, tanggal pembelian/kedaluwarsa, serta URL foto opsional melalui formulir.
- **Read**: Melihat daftar dan detail makanan milik sendiri, mencari berdasarkan nama, menyaring berdasarkan status, serta melihat penanda kedaluwarsa.
- **Update**: Mengedit informasi makanan, menandai sudah habis, atau menyimpan kembali. Publikasi melalui SharedPost mengubah status makanan menjadi ditawarkan.
- **Delete**: Menghapus makanan milik sendiri beserta penawaran SharedPost yang terkait.

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

## Peran Pengguna

**Guest (belum login)**: Melihat landing page
**User (setelah login)**: Mengelola inventori makanan sendiri, mempublikasikan dan mengelola penawaran di papan berbagi, melihat kontak donor, dan mengelola profil dan notifikasi sendiri.
**Admin**: Memoderasi pengumuman yang tidak pantas dan mengelola data pengguna

**Alur singkat**: Jika pengguna merasa tidak sanggup menghabiskan makanan tersebut, mereka dapat memublikasikannya ke Papan Berbagi. Pengguna lain dapat membuka antarmuka peta interaktif untuk melihat sebaran makanan gratis di sekitar mereka. Ketika sebuah titik (pin) di peta ditekan, aplikasi akan langsung membuka halaman detail pengumuman tersebut. Dari sana, pencari makanan dapat menekan tombol kontak yang langsung mengarahkan mereka ke aplikasi pesan singkat (seperti WhatsApp) milik pendonor. Seluruh proses transaksi dan pengambilan dilakukan secara mandiri (peer-to-peer).

## Tautan deployment PWS

https://justin-evan-titiklapar.pws.cs.ui.ac.id/

### Konfigurasi deployment

Gunakan [.env.prod.example](.env.prod.example) sebagai daftar variabel yang perlu
diisi melalui panel environment PWS. File contoh tidak otomatis dibaca aplikasi.
Sebelum menjalankan versi ini di server:

- Isi `PRODUCTION=True`, `DEBUG=False`, dan kredensial PostgreSQL sesuai PWS.
- Isi `SECRET_KEY` dengan kunci acak baru yang hanya disimpan di environment server.
  Aplikasi menolak berjalan dalam mode produksi jika nilainya kosong. Pergantian
  kunci membuat pengguna perlu login ulang.
- Pastikan `ALLOWED_HOSTS` berisi nama domain tanpa skema, sedangkan
  `CSRF_TRUSTED_ORIGINS` dan `SITE_URL` memakai URL lengkap dengan `https://`.
- Jika email ingin dikirim ke inbox, isi konfigurasi SMTP dan jadwalkan
  `python manage.py send_food_reminders` setiap hari. Backend console hanya
  mencetak email ke log.

Untuk membuat kunci baru, jalankan perintah ini di terminal sendiri lalu salin
hasilnya ke environment PWS, bukan ke repository:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Pada proses deployment, jalankan `python manage.py migrate --noinput` dan
`python manage.py collectstatic --noinput`. Setelah environment siap, jalankan
`python manage.py check --deploy` dengan konfigurasi server. Cookie login dan
CSRF otomatis dibatasi ke HTTPS ketika `PRODUCTION=True`; lokal tetap mendukung
HTTP dengan `PRODUCTION=False`.

Pengaturan kepercayaan header proxy, redirect HTTPS, dan HSTS perlu disesuaikan
dengan proxy PWS. Pengaturan tersebut tidak diaktifkan otomatis. Pemeriksaan
deployment masih dapat memberi peringatan redirect HTTPS/HSTS, sehingga
penanggung jawab server perlu memverifikasi pengaturan HTTPS di proxy.

Workflow GitHub saat ini melakukan deployment saat ada push ke `pws-branch`.
Merge ke `main` saja belum memperbarui aplikasi yang tayang. Setelah deployment,
periksa login dan pengiriman form melalui domain HTTPS PWS.

## Tautan Figma

https://www.figma.com/design/r3aIEwY6EmWnxDocq8Rrl3/Projek-PBP-B12?node-id=0-1&t=RJOL7DroOzRv7Kqf-1

## Panduan integrasi terbaru

Alur akun/email, lokasi tersimpan + GPS, inventori, penawaran, peta, pengingat, migrasi, dan pengujian dijelaskan dalam [docs/integrasi.md](docs/integrasi.md).
