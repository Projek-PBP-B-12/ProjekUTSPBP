(function () {
  'use strict';

  document.querySelectorAll('[data-delete-location]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!window.confirm('Hapus lokasi ini dari daftar lokasimu?')) event.preventDefault();
    });
  });

  const form = document.getElementById('location-form');
  if (!form) return;
  const latitude = document.getElementById('id_latitude');
  const longitude = document.getElementById('id_longitude');
  const gpsButton = document.getElementById('use-current-location');
  const gpsStatus = document.getElementById('location-gps-status');
  const searchInput = document.getElementById('location-address-search');
  const searchButton = document.getElementById('location-address-button');
  const searchStatus = document.getElementById('location-search-status');
  const resultsList = document.getElementById('location-search-results');

  function fillCoordinates(lat, lng) {
    lat = Number(lat);
    lng = Number(lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return false;
    latitude.value = lat.toFixed(6);
    longitude.value = lng.toFixed(6);
    return true;
  }

  gpsButton.addEventListener('click', function () {
    if (!window.isSecureContext || !navigator.geolocation) {
      gpsStatus.textContent = 'GPS membutuhkan HTTPS atau localhost dan peramban yang mendukung lokasi. Isi koordinat manual atau gunakan pencarian.';
      return;
    }
    gpsButton.disabled = true;
    gpsStatus.textContent = 'Meminta izin lokasi dari peramban...';
    navigator.geolocation.getCurrentPosition(function (position) {
      gpsButton.disabled = false;
      if (!fillCoordinates(position.coords.latitude, position.coords.longitude)) {
        gpsStatus.textContent = 'Koordinat GPS tidak valid. Gunakan pencarian atau isi manual.';
        return;
      }
      const accuracy = Math.round(position.coords.accuracy);
      gpsStatus.textContent = 'Koordinat terisi' + (Number.isFinite(accuracy) ? ' (perkiraan ketelitian ' + accuracy + ' meter)' : '') + '. Periksa dan beri nama lokasi, lalu tekan Simpan lokasi.';
    }, function (error) {
      gpsButton.disabled = false;
      const messages = {
        1: 'Izin lokasi ditolak. Kamu tetap bisa menggunakan pencarian atau mengisi koordinat manual.',
        2: 'Lokasi perangkat belum tersedia. Coba lagi, gunakan pencarian, atau isi koordinat manual.',
        3: 'Pencarian GPS melewati batas waktu. Coba lagi, gunakan pencarian, atau isi koordinat manual.',
      };
      gpsStatus.textContent = messages[error.code] || 'GPS tidak tersedia. Gunakan pencarian atau isi koordinat manual.';
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 });
  });

  async function searchAddress() {
    if (searchButton.disabled) return;
    const query = searchInput.value.trim();
    if (query.length < 3) {
      searchStatus.textContent = 'Tulis minimal 3 karakter.';
      return;
    }
    searchButton.disabled = true;
    resultsList.replaceChildren();
    searchStatus.textContent = 'Mencari tempat...';
    try {
      const response = await fetch(form.dataset.searchUrl + '?q=' + encodeURIComponent(query), { credentials: 'same-origin' });
      const results = await response.json();
      if (!response.ok) throw new Error(results.message || 'Pencarian sedang tidak tersedia.');
      searchStatus.textContent = results.length ? 'Pilih tempat yang sesuai. Koordinat belum disimpan.' : 'Tempat tidak ditemukan. Coba nama area lain atau isi koordinat manual.';
      results.forEach(function (result) {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = result.display_name;
        button.className = 'location-result';
        button.addEventListener('click', function () {
          if (!fillCoordinates(result.latitude, result.longitude)) {
            searchStatus.textContent = 'Hasil pencarian tidak memiliki koordinat valid.';
            return;
          }
          const area = document.getElementById('id_area_name');
          if (!area.value.trim()) area.value = result.area_name;
          searchStatus.textContent = 'Dipilih: ' + result.display_name + '. Periksa nama dan koordinat, lalu tekan Simpan lokasi.';
          resultsList.replaceChildren();
        });
        item.appendChild(button);
        resultsList.appendChild(item);
      });
    } catch (error) {
      searchStatus.textContent = error.message || 'Pencarian sedang tidak tersedia. Isi koordinat manual.';
    } finally {
      searchButton.disabled = false;
    }
  }
  searchButton.addEventListener('click', searchAddress);
  searchInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      searchAddress();
    }
  });
})();
