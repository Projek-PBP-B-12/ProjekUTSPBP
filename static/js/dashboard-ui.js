(() => {
  const toggle = document.querySelector('.dashboard-menu-toggle');
  const close = document.querySelector('.dashboard-menu-close');
  const backdrop = document.querySelector('.dashboard-menu-backdrop');
  const sidebar = document.querySelector('#sidebar');

  function setMenu(open, restoreFocus = false) {
    document.body.classList.toggle('dashboard-menu-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    backdrop.hidden = !open;
    if (open) close.focus();
    else if (restoreFocus) toggle.focus();
  }

  toggle.addEventListener('click', () => setMenu(true));
  close.addEventListener('click', () => setMenu(false, true));
  backdrop.addEventListener('click', () => setMenu(false, true));
  document.addEventListener('keydown', event => {
    if (!document.body.classList.contains('dashboard-menu-open')) return;
    if (event.key === 'Escape') setMenu(false, true);
    if (event.key === 'Tab') {
      const items = [...sidebar.querySelectorAll('a[href], button:not(:disabled)')];
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    }
  });
  window.matchMedia('(min-width: 801px)').addEventListener('change', event => {
    if (event.matches) setMenu(false);
  });
})();
