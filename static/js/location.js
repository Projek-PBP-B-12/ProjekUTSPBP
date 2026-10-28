(function () {
  const pins = JSON.parse(document.getElementById('pins-data').textContent);
  const center = JSON.parse(document.getElementById('map-center-data').textContent);
  const hint = document.getElementById('map-search-hint');
  if (typeof L === 'undefined') {
    hint.textContent = 'Peta belum dapat dimuat. Kamu tetap bisa membuka penawaran melalui daftar di bawah.';
    document.getElementById('map').hidden = true;
    document.getElementById('map-reset-center').disabled = true;
    document.getElementById('map-show-all').disabled = true;
    document.querySelector('#map-search-form button').disabled = true;
    return;
  }

  const initialCenter = [Number(center.latitude), Number(center.longitude)];
  const map = L.map('map').setView(initialCenter, 14);

  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    referrerPolicy: 'strict-origin-when-cross-origin',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function formatDistance(km) {
    if (km < 1) return Math.round(km * 1000) + ' m';
    return km.toLocaleString('id-ID', { maximumFractionDigits: 1 }) + ' km';
  }

  // Teks dari data dipasang lewat textContent, bukan innerHTML,
  // supaya judul/deskripsi buatan pengguna nanti tidak bisa menyisipkan HTML.
  function buildPopup(pin) {
    const root = el('div');

    const photo = pin.photo_url ? el('img', 'map-popup-photo') : el('div', 'map-popup-photo');
    if (pin.photo_url) {
      photo.src = pin.photo_url;
      photo.alt = pin.title;
    }
    root.appendChild(photo);

    root.appendChild(el('h3', 'map-popup-title', pin.title));
    if (pin.distance_km != null) {
      root.appendChild(el('p', 'map-popup-distance', 'Sekitar ' + formatDistance(pin.distance_km) + ' dari lokasi bawaan Anda'));
    }
    if (pin.area_name) root.appendChild(el('p', 'map-popup-area', pin.area_name));
    root.appendChild(el('p', 'map-popup-desc', pin.description));

    const claim = el('a', 'button button-primary map-popup-claim', 'Lihat penawaran');
    claim.href = pin.detail_url || '#';
    root.appendChild(claim);

    return root;
  }

  pins.forEach(function (pin, index) {
    const icon = L.divIcon({
      className: 'map-pin',
      html: String(index + 1),
      iconSize: [36, 36],
    });

    L.marker([Number(pin.latitude), Number(pin.longitude)], { icon: icon, title: pin.title })
      .addTo(map)
      .bindPopup(buildPopup(pin), { className: 'map-popup', minWidth: 280, maxWidth: 280 });
  });

  document.getElementById('map-reset-center').addEventListener('click', function () {
    map.closePopup();
    map.flyTo(initialCenter, 14);
  });
  document.getElementById('map-show-all').addEventListener('click', function () {
    if (!pins.length) return;
    map.fitBounds(
      pins.map(function (pin) { return [Number(pin.latitude), Number(pin.longitude)]; }),
      { padding: [60, 60], maxZoom: 16 }
    );
  });

  const form = document.getElementById('map-search-form');
  const input = document.getElementById('map-search-input');
  const searchButton = form.querySelector('button[type="submit"]');

  // Pencarian hanya dijalankan saat Enter ditekan, bukan tiap ketikan (aturan Nominatim).
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (searchButton.disabled) return;
    const query = input.value.trim();

    if (query.length < 3) {
      hint.textContent = 'Tulis minimal 3 karakter.';
      return;
    }

    hint.textContent = 'Mencari...';
    searchButton.disabled = true;
    try {
      const response = await fetch(form.dataset.searchUrl + '?q=' + encodeURIComponent(query));
      const results = await response.json();
      if (!response.ok) throw new Error(results.message || 'Pencarian sedang tidak tersedia.');

      if (!results.length) {
        hint.textContent = 'Lokasi tidak ditemukan. Coba nama lain.';
        return;
      }

      map.closePopup();
      map.flyTo([Number(results[0].latitude), Number(results[0].longitude)], 16);
      hint.textContent = results[0].display_name;
    } catch (error) {
      hint.textContent = error.message || 'Pencarian sedang tidak tersedia.';
    } finally {
      searchButton.disabled = false;
    }
  });
})();
