(() => {
  function hideFailedPhoto(image) {
    if (image.matches('img.food-photo')) image.hidden = true;
  }
  document.addEventListener('error', event => {
    if (event.target instanceof HTMLImageElement) hideFailedPhoto(event.target);
  }, true);
  function checkPhotos(root) {
    root.querySelectorAll('img.food-photo').forEach(image => {
      if (image.complete && image.naturalWidth === 0) hideFailedPhoto(image);
    });
  }
  checkPhotos(document);
  const toggle = document.querySelector('.menu-toggle');
  const backdrop = document.querySelector('.sidebar-backdrop');
  function setMenu(open) {
    document.body.classList.toggle('menu-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    backdrop.hidden = !open;
    if (open) document.querySelector('.menu-close').focus();
  }
  toggle.addEventListener('click', () => setMenu(toggle.getAttribute('aria-expanded') !== 'true'));
  document.querySelector('.menu-close').addEventListener('click', () => { setMenu(false); toggle.focus(); });
  backdrop.addEventListener('click', () => setMenu(false));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') { setMenu(false); } });
  document.addEventListener('click', event => { if (event.target.closest('[data-close-form]')) document.querySelector('#post-form').replaceChildren(); });
  document.body.addEventListener('htmx:afterSwap', event => {
    checkPhotos(event.detail.target);
    if (event.detail.target.id === 'post-form') {
      const field = event.detail.target.querySelector('select:not(:disabled), textarea');
      if (field) field.focus({preventScroll: true});
      event.detail.target.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }
  });
  document.body.addEventListener('htmx:responseError', () => { const feedback = document.querySelector('#board-feedback'); if (feedback) feedback.textContent = 'Permintaan gagal. Muat ulang halaman dan coba lagi.'; });
  document.body.addEventListener('htmx:sendError', () => { const feedback = document.querySelector('#board-feedback'); if (feedback) feedback.textContent = 'Koneksi terputus. Periksa jaringan lalu coba lagi.'; });
})();
