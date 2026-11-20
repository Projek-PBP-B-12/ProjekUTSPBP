# AI Disclosure — Location dan Integrasi Antar Modul

**Alat AI:** Claude, Gemini

## Pernyataan penggunaan AI

Saya menggunakan Claude dan Gemini pengembangan modul Location. Bantuan AI meliputi penjelasan konsep Django, penyusunan dan perbaikan kode, penelusuran error, penulisan pengujian otomatis, integrasi dengan API, dan integrasi dengan modul-modul lain.

## Cakupan bantuan AI

| Bagian                                  | Bantuan yang digunakan                                                                                                                                                                                                |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model Location dan Relasi Data          | Membantu menyusun struktur model `Location` pada `models.py`, mendefinisikan kolom koordinat dan alamat, serta mengatur relasi data dengan `UserProfile` dan `SharedPost`.                                            |
| Integrasi API Nominatim (OpenStreetMap) | Membantu penyusunan logika di services.py untuk menghubungkan aplikasi dengan API Nominatim, menangani proses geocoding dan reverse geocoding, serta mengelola batas pencarian dan error handling dari API eksternal. |
| Forms dan Views                         | Membantu membuat validasi data lokasi pada `forms.py`, menyusun penanganan request CRUD lokasi di `views.py`, serta mengatur penentuan lokasi default pengguna.                                                       |
| Integrasi SharedPost                    | Membantu menghubungkan lokasi yang dipilih/disimpan pengguna dengan postingan di modul SharedPost untuk menentukan titik pengambilan/penawaran makanan.                                                               |
| Unit Testing                            | Membantu menyusun skenario unit test untuk menguji alur CRUD lokasi, pencarian berbasis API, penanganan kegagalan koneksi API, dan validasi relasi antar modul.                                                       |
| Refactoring & Penelusuran Error         | Membantu melacak bug, memberikan saran perbaikan sintaks, serta mengoptimalkan struktur kode agar lebih efisien dan rapi di seluruh berkas modul.                                                                     |

Berkas utama Location meliputi [models.py](models.py), [forms.py](forms.py), [views.py](views.py), [urls.py](urls.py), dan [services.py](services.py).

## Peran saya selama pengembangan

Saya memberikan penjelasan mengenai peran modul Location. Hasil dari AI kemudian saya revisi lagi sesuai dengan kebutuhan. Apabila terdapat misinterpretasi, maka saya akan konfirmasi kembali dan menanyakan kode yang lebih efisien. Saya juga memberi konteks tambahan berupa kode-kode dari SharedPost dan UserProfile supaya kode bisa terintegrasi.

Contohnya adalah ketika revisi pembuatan model Location agar terintegrasi dengan SharedPost dan UserProfile, menghubungkan dengan API Nomatim (OpenStreetMap), dan meninjau ulang konsinstensi kode.
