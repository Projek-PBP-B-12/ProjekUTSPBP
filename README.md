# Projek UTS PBP - B Kelompok 12

## Nama Anggota
1. GHULAM MUHAMMAD IHSAN : 2506656766  
2. Muh. Agra Putra Davyza Chaniago : 2506624833  
3. ANINDYA RAIHANI HASSAN : 2506553295  
4. ILMAN ZIDNI : 2506621951  
5. JUSTIN EVAN HALIM SAPUTRA : 2506549386  

## Latar Belakang Aplikasi
 Hal ini berawal dari concern kita terhadap masyarakat terutama mahasiswa yang tinggal di kos dan sering menyimpan makanan di kulkas bersama. Dikarenakan makanan yang disimpan mahasiswa tergolong banyak dan lamanya waktu penyimpanan yang tidak terdata, terkadang lupa bahwa makanan tersebut sudah kedaluwarsa. Maka dari itu solusi dari kami adalah TitikLapar. TitikLapar, Website ini ini adalah Personal Food Tracker & Papan Pengumuman Spasial yang dirancang untuk menekan angka food waste. Pengguna dapat mencatat makanan yang mereka beli melalui antarmuka yang simpel dengan memasukkan nama barang dan tanggal pembelian. Jika pengguna tidak mengetahui tanggal kedaluwarsa secara pasti, sistem akan secara otomatis mengestimasi expired date berdasarkan basis data ketahanan pangan bawaan. Ketika sebuah item makanan mendekati masa kedaluwarsa (misalnya H-3), sistem akan mengirimkan push notification sebagai pengingat. Di titik ini, pengguna diberikan opsi praktis: mengonsumsinya segera, atau membagikannya secara gratis melalui Forum Donasi terintegrasi. Di dalam forum ini, makanan yang hampir kedaluwarsa namun masih layak konsumsi dapat diklaim oleh pengguna lain di sekitar mereka, menciptakan ekosistem sirkular yang saling menguntungkan dan ramah lingkungan.

## Daftar Modul
### UserProfile
User berperan sebagai fondasi identitas dan pusat komunikasi antar pengguna di dalam aplikasi. Entitas ini tidak hanya menyimpan data standar seperti nama pengguna dan kata sandi untuk autentikasi, tetapi juga memegang peran krusial dalam sistem transaksi mandiri melalui atribut kontak eksternal, seperti tautan WhatsApp atau ID Line. Selain itu, model ini menyimpan koordinat lokasi bawaan pengguna agar saat fitur peta dibuka, antarmuka dapat langsung memusatkan titik area pada lokasi tersebut tanpa harus selalu menunda pemuatan demi menunggu akses GPS dari peramban.
(Penanggung jawab modul : Ghulam)  

### FoodItem
FoodItem bertindak sebagai mesin operasional utama dari fitur pelacak inventori pribadi. Entitas ini bertanggung jawab menyimpan seluruh data operasional makanan yang dimasukkan pengguna, mulai dari nama, kategori, tanggal pembelian, hingga tanggal kedaluwarsa. Model ini menjadi acuan mutlak bagi sistem penjadwal di latar belakang untuk menghitung sisa hari kelayakan konsumsi, serta memiliki penanda status yang secara tegas membedakan apakah suatu makanan masih tersimpan secara privat, sudah habis dikonsumsi, atau sedang ditawarkan ke publik.  
(Penanggung jawab modul : Zidni)  

### SharedPost
SharedPost merepresentasikan data spasial di atas papan pengumuman dan peta interaktif. Entitas ini memiliki relasi langsung dengan model makanan sebelumnya, di mana ia mengekstrak informasi barang dan memadukannya dengan titik pasti garis lintang dan garis bujur yang akan dirender menjadi pin lokasi oleh OpenStreetMap dan Leaflet.js. Peran utamanya adalah memastikan tabel inventori pribadi tidak tercampur dengan kueri data publik, sekaligus menyimpan deskripsi pengambilan dari pendonor dan memantau status keaktifan agar pin lokasi dapat disembunyikan seketika saat makanan sudah diambil orang lain.  
(Penanggung jawab modul : Justin)  

### LokasiPeta
Modul spasial ini secara khusus dirancang untuk "berbicara" dengan Google Maps API. Modul ini hanya peduli pada tiga hal: Garis Lintang (Latitude), Garis Bujur (Longitude), dan nama area umum (misalnya: "Kecamatan Beji", untuk menjaga privasi alamat persis). Dengan menjadikan lokasi sebagai modul tersendiri (normalisasi data), sistem dapat merender ratusan pin atau marker di atas peta secara ringan dan cepat tanpa perlu menarik seluruh data pengguna atau data makanan yang tidak diperlukan oleh peta.  
(Penanggung jawab modul : Anin)  

### Notification
Notofication memiliki peran sebagai kotak masuk atau riwayat peringatan yang menjembatani sistem otomatisasi di belakang layar dengan pengguna akhir. Peran utamanya adalah menerima dan menyimpan rekaman pesan peringatan yang dihasilkan oleh sistem ketika ada makanan yang mendekati batas waktu kedaluwarsa. Entitas ini merekam tenggat waktu pembuatan pesan dan status keterbacaan, sehingga aplikasi dapat menampilkan atau menyembunyikan indikator visual berwarna pada antarmuka sesuai dengan interaksi pengguna terhadap peringatan tersebut.
(Penanggung jawab modul : Agra)  

### Sumber/dokumentasi Public API
1. *OpenStreetMap (OSM) & Leaflet.js:* Kombinasi layanan data peta dan library antarmuka. Digunakan untuk menampilkan peta interaktif dan meletakkan marker (titik lokasi) makanan di perangkat pengguna.
2. *Nominatim API:* Layanan geocoding bawaan dari OpenStreetMap. Digunakan untuk mengubah teks alamat yang diinput pengguna menjadi koordinat spasial (Latitude/Longitude) agar bisa dirender ke dalam peta.
3. *Open Food Facts API:* Basis data produk makanan global. Dapat disuntikkan pada modul input inventori agar sistem bisa melakukan autofill (pengisian otomatis) nama dan standar ketahanan makanan saat pengguna mengetikkan nama barang.  

### Peran Pengguna 
Jika pengguna merasa tidak sanggup menghabiskan makanan tersebut, mereka dapat memublikasikannya ke "Papan Pengumuman". Pengguna lain dapat membuka antarmuka peta interaktif untuk melihat sebaran makanan gratis di sekitar mereka. Ketika sebuah titik (pin) di peta ditekan, aplikasi akan langsung membuka halaman detail pengumuman tersebut. Dari sana, pencari makanan dapat menekan tombol kontak yang langsung mengarahkan mereka ke aplikasi pesan singkat (seperti WhatsApp) milik pendonor. Seluruh proses transaksi dan pengambilan dilakukan secara mandiri (peer-to-peer).

## Tautan deployment PWS

## Tautan Figma
