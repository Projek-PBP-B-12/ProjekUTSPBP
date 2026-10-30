(function () {
  const pins = JSON.parse(document.getElementById('pins-data').textContent);
  const center = JSON.parse(document.getElementById('map-center-data').textContent);
  const selectedPostId = JSON.parse(document.getElementById('selected-post-data').textContent);
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
  map.zoomControl.setPosition('bottomright');

  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    referrerPolicy: 'strict-origin-when-cross-origin',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  let activePopup = null;
  map.on('popupopen', function (event) { activePopup = event.popup; });
  map.on('popupclose', function () { activePopup = null; });
  map.on('resize', function () {
    // Ukuran daftar berubah mengikuti layar. Hitung ulang posisi popup agar
    // judul dan tombol tetap berada di dalam peta setelah layar diputar/diubah.
    if (activePopup) activePopup.update();
  });

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
  function buildOffer(pin) {
    const root = el('article', 'map-popup-offer');
    if (pin.id === selectedPostId) root.classList.add('map-popup-offer-selected');

    const photo = el('div', 'map-popup-photo');
    const photoFallback = el('span', 'map-popup-photo-placeholder', 'Foto tidak tersedia');
    photo.appendChild(photoFallback);
    if (pin.photo_url) {
      const image = el('img', 'map-popup-image');
      image.alt = pin.title;
      image.referrerPolicy = 'no-referrer';
      image.addEventListener('load', function () { photoFallback.hidden = true; });
      image.addEventListener('error', function () {
        image.remove();
        photoFallback.hidden = false;
      }, {once: true});
      photo.appendChild(image);
      image.src = pin.photo_url;
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
    claim.setAttribute('aria-label', 'Lihat penawaran ' + pin.title);
    root.appendChild(claim);

    return root;
  }

  function buildPopup(group) {
    const root = el('div');
    if (group.length > 1) {
      root.appendChild(el('h2', 'map-popup-heading', group.length + ' penawaran di area ini'));
      root.appendChild(el('p', 'map-popup-help', 'Gulir untuk melihat semua makanan.'));
    }
    const list = el('div', 'map-popup-offers');
    list.tabIndex = 0;
    list.setAttribute('role', 'region');
    list.setAttribute('aria-label', 'Daftar penawaran di titik ini');
    // Penawaran yang dibuka dari halaman detail selalu terlihat paling atas.
    const selected = group.find(function (pin) { return pin.id === selectedPostId; });
    const ordered = selected ? [selected].concat(group.filter(function (pin) { return pin !== selected; })) : group;
    ordered.forEach(function (pin) { list.appendChild(buildOffer(pin)); });
    root.appendChild(list);
    return root;
  }

  // Koordinat publik sudah dibulatkan oleh server. Kelompokkan titik yang sama
  // agar tidak ada marker yang menutupi penawaran lain di area tersebut.
  const groups = new Map();
  pins.forEach(function (pin) {
    const key = Number(pin.latitude) + ',' + Number(pin.longitude);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(pin);
  });

  let selectedMarker = null;
  let selectedTitle = '';
  groups.forEach(function (group) {
    const pin = group[0];
    const selected = group.find(function (offer) { return offer.id === selectedPostId; });
    const label = group.length + ' penawaran di area ' + pin.area_name;
    const icon = L.divIcon({
      className: selected ? 'map-pin map-pin-selected' : 'map-pin',
      html: String(group.length),
      iconSize: [36, 36],
    });

    const marker = L.marker([Number(pin.latitude), Number(pin.longitude)], {
      icon: icon, title: label, alt: label, zIndexOffset: selected ? 1000 : 0,
    })
      .addTo(map)
      .bindPopup(buildPopup(group), { className: 'map-popup', minWidth: 240, maxWidth: 280 });
    marker.getElement().setAttribute('aria-label', label);
    if (selected) {
      selectedMarker = marker;
      selectedTitle = selected.title;
    }
  });

  if (selectedMarker) {
    map.setView(selectedMarker.getLatLng(), 16, { animate: false });
    selectedMarker.openPopup();
    hint.textContent = 'Menampilkan area penawaran ' + selectedTitle + '. Titik pengambilan disepakati dengan donor.';
  }

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
