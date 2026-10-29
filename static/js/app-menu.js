(() => {
  const sidebar = document.querySelector('#sidebar');
  const header = document.querySelector('.app-mobile-header');
  const toggle = document.querySelector('.app-menu-toggle');
  const close = document.querySelector('.app-menu-close');
  const backdrop = document.querySelector('.app-sidebar-backdrop');
  const main = document.querySelector('.app-main');
  if (!sidebar || !header || !toggle || !close || !backdrop || !main) return;

  const mobile = window.matchMedia('(max-width: 800px)');
  let isOpen = false;

  function setMenu(open, restoreFocus = true) {
    const wasOpen = isOpen;
    const hadSidebarFocus = sidebar.contains(document.activeElement);
    isOpen = Boolean(open && mobile.matches);
    document.body.classList.toggle('app-menu-open', isOpen);
    toggle.setAttribute('aria-expanded', String(isOpen));
    backdrop.hidden = !isOpen;
    sidebar.inert = mobile.matches && !isOpen;
    main.inert = isOpen;
    header.inert = isOpen;

    if (isOpen) {
      sidebar.removeAttribute('aria-hidden');
      sidebar.setAttribute('role', 'dialog');
      sidebar.setAttribute('aria-modal', 'true');
      if (!wasOpen) sidebar.scrollTop = 0;
      close.focus({preventScroll: true});
    } else {
      sidebar.removeAttribute('role');
      sidebar.removeAttribute('aria-modal');
      // Move focus before hiding the mobile drawer from assistive technology.
      if (restoreFocus && (wasOpen || (mobile.matches && hadSidebarFocus))) {
        if (mobile.matches) toggle.focus({preventScroll: true});
        else sidebar.querySelector('.sidebar-item[aria-current="page"], .sidebar-item')?.focus({preventScroll: true});
      }
      if (mobile.matches) sidebar.setAttribute('aria-hidden', 'true');
      else sidebar.removeAttribute('aria-hidden');
    }
  }

  // Only hide the mobile sidebar once its controls are ready. Without JavaScript,
  // the original navigation stays visible and usable.
  document.body.classList.add('app-menu-ready');
  setMenu(false);
  toggle.addEventListener('click', () => setMenu(!isOpen));
  close.addEventListener('click', () => setMenu(false));
  backdrop.addEventListener('click', () => setMenu(false));
  sidebar.addEventListener('click', event => {
    if (event.target.closest('a[href]')) setMenu(false, false);
  });
  sidebar.addEventListener('submit', () => setMenu(false, false));

  document.addEventListener('keydown', event => {
    if (!isOpen) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      setMenu(false);
    } else if (event.key === 'Tab') {
      const items = [...sidebar.querySelectorAll('a[href], button:not(:disabled), [tabindex="0"]')]
        .filter(element => element.getClientRects().length > 0);
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || !sidebar.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !sidebar.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  mobile.addEventListener('change', () => setMenu(false));
  window.addEventListener('pageshow', () => setMenu(false, false));
})();
