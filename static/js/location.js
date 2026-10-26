(function () {
  const pins = JSON.parse(document.getElementById('pins-data').textContent);

  const map = L.map('map').setView([-6.366, 106.818], 15);

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
      root.appendChild(el('p', 'map-popup-distance', formatDistance(pin.distance_km) + ' dari lokasi Anda'));
    }
    root.appendChild(el('p', 'map-popup-desc', pin.description));

    const claim = el('a', 'button button-primary map-popup-claim', 'Klaim');
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

  if (pins.length) {
    map.fitBounds(
      pins.map(function (pin) { return [Number(pin.latitude), Number(pin.longitude)]; }),
      { padding: [60, 60], maxZoom: 16 }
    );
  }

  const form = document.getElementById('map-search-form');
  const input = document.getElementById('map-search-input');
  const hint = document.getElementById('map-search-hint');

  // Pencarian hanya dijalankan saat Enter ditekan, bukan tiap ketikan (aturan Nominatim).
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    const query = input.value.trim();

    if (query.length < 3) {
      hint.textContent = 'Tulis minimal 3 karakter.';
      return;
    }

    hint.textContent = 'Mencari...';
    try {
      const response = await fetch(form.dataset.searchUrl + '?q=' + encodeURIComponent(query));
      if (!response.ok) throw new Error('search failed');
      const results = await response.json();

      if (!results.length) {
        hint.textContent = 'Lokasi tidak ditemukan. Coba nama lain.';
        return;
      }

      map.closePopup();
      map.flyTo([Number(results[0].latitude), Number(results[0].longitude)], 16);
      hint.textContent = results[0].display_name;
    } catch (error) {
      hint.textContent = 'Pencarian sedang tidak tersedia.';
    }
  });
})();