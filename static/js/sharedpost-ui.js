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
  const filters = document.querySelector('#board-filters');
  function resetPage(event) {
    if (event.target.matches('input:not([type=hidden]), select')) {
      document.querySelector('#board-page').value = '1';
    }
  }
  if (filters) {
    filters.addEventListener('input', resetPage);
    filters.addEventListener('change', resetPage);
  }
  let firstNewCard = null;
  document.addEventListener('click', event => {
    if (event.target.closest('.load-more')) firstNewCard = document.querySelectorAll('.post-card').length;
  });
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
    if (event.detail.target.id === 'post-list' && firstNewCard !== null) {
      const card = event.detail.target.querySelectorAll('.post-card')[firstNewCard];
      if (card) card.querySelector('.post-title a').focus({preventScroll: true});
      firstNewCard = null;
    }
    if (event.detail.target.id === 'post-form') {
      const field = event.detail.target.querySelector('select:not(:disabled), textarea');
      if (field) field.focus({preventScroll: true});
      event.detail.target.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }
  });
  document.body.addEventListener('htmx:responseError', () => { firstNewCard = null; const feedback = document.querySelector('#board-feedback'); if (feedback) feedback.textContent = 'Permintaan gagal. Muat ulang halaman dan coba lagi.'; });
  document.body.addEventListener('htmx:sendError', () => { firstNewCard = null; const feedback = document.querySelector('#board-feedback'); if (feedback) feedback.textContent = 'Koneksi terputus. Periksa jaringan lalu coba lagi.'; });
})();
