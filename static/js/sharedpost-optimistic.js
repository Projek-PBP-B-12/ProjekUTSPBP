(() => {
  const board = document.querySelector('#post-list');
  const filters = document.querySelector('#board-filters');
  const feedback = document.querySelector('#board-feedback');
  if (!board || !filters || !feedback) return;

  const reads = new Set();
  const optimisticRequests = new WeakSet();
  let pending = null;

  function announce(message, state) {
    feedback.dataset.state = state;
    feedback.textContent = message;
  }

  function affectsBoard(detail) {
    return detail.target === board || detail.target?.id === 'post-form';
  }

  // A mutation must not race a filter refresh or another mutation. Existing
  // reads are aborted before the optimistic change; new requests wait for retry.
  document.body.addEventListener('htmx:beforeRequest', event => {
    if (pending && affectsBoard(event.detail)) {
      event.preventDefault();
      return;
    }
    if (event.detail.target === board && event.detail.requestConfig.verb === 'get') {
      reads.add(event.detail.xhr);
    }
  });

  document.body.addEventListener('htmx:beforeSend', event => {
    const form = event.detail.elt.closest('form[data-optimistic-action]');
    if (!form || !['delete', 'complete'].includes(form.dataset.optimisticAction)) return;
    const card = form.closest('.post-card');
    if (!card || pending) return;

    // beforeSend runs after confirmation and parameter collection. Keeping the
    // original DOM nodes lets rollback preserve their order and HTMX bindings.
    pending = {
      xhr: event.detail.xhr,
      action: form.dataset.optimisticAction,
      card,
      button: form.querySelector('button[type="submit"]'),
      reconciled: false,
      counts: [...document.querySelectorAll('#all-offers-count, [data-total-count], [data-visible-count]')]
        .map(node => ({node, text: node.textContent})),
      controls: [...document.querySelectorAll('#board-filters input, #board-filters select, #post-list button, #post-form input, #post-form select, #post-form textarea, #post-form button')]
        .filter(control => !control.disabled),
    };
    optimisticRequests.add(pending.xhr);
    for (const xhr of reads) xhr.abort();
    reads.clear();
    for (const control of pending.controls) control.disabled = true;
    for (const {node, text} of pending.counts) {
      node.textContent = String(Math.max(0, Number(text) - 1));
    }
    card.hidden = true;
    board.setAttribute('aria-busy', 'true');
    announce(pending.action === 'delete' ? 'Menghapus penawaran…' : 'Menandai makanan sudah diambil…', 'pending');
    feedback.focus({preventScroll: true});
  });

  document.body.addEventListener('htmx:beforeSwap', event => {
    if (!pending || event.detail.xhr !== pending.xhr) return;
    // A login redirect, empty response, or unrelated HTML is not confirmation
    // that the mutation completed. Never swap such a response into the board.
    if (event.detail.xhr.getResponseHeader('X-SharedPost-Action') !== pending.action) {
      event.detail.shouldSwap = false;
      event.detail.isError = true;
    }
  });

  document.body.addEventListener('htmx:afterSwap', event => {
    if (pending && event.detail.xhr === pending.xhr && event.detail.target === board) {
      pending.reconciled = true;
    }
  });

  document.body.addEventListener('htmx:afterRequest', event => {
    const wasRead = reads.delete(event.detail.xhr);
    if (!pending || event.detail.xhr !== pending.xhr) {
      if (wasRead && event.detail.successful && feedback.querySelector('button')) {
        announce('Daftar penawaran telah diperbarui.', 'success');
      }
      return;
    }
    const state = pending;
    pending = null;
    board.removeAttribute('aria-busy');
    for (const control of state.controls) {
      if (control.isConnected) control.disabled = false;
    }
    const returnFocus = document.activeElement === feedback || document.activeElement === document.body;
    if (event.detail.successful && state.reconciled) {
      announce(state.action === 'delete' ? 'Penawaran berhasil dihapus.' : 'Penawaran ditandai sudah diambil.', 'success');
      if (returnFocus) {
        const next = board.querySelector('.post-title a') || document.querySelector('a[href][hx-target="#post-form"]');
        next?.focus({preventScroll: true});
      }
      return;
    }

    // Do not insert detached snapshots into a newer board. Network errors can
    // occur after a server commit, so offer a fresh read instead of promising
    // that the database was rolled back as well.
    if (state.card.isConnected) state.card.hidden = false;
    for (const {node, text} of state.counts) {
      if (node.isConnected) node.textContent = text;
    }
    const retryAfter = Math.max(1, Number.parseInt(state.xhr.getResponseHeader('Retry-After'), 10) || 60);
    const message = state.xhr.status === 429
      ? `Terlalu banyak perubahan. Coba lagi dalam ${retryAfter} detik. Tampilan dipulihkan.`
      : 'Permintaan belum dapat dikonfirmasi. Tampilan dipulihkan; periksa ulang daftar untuk memastikan status terbaru.';
    announce(message, 'error');
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'button secondary';
    retry.textContent = 'Periksa ulang daftar';
    retry.addEventListener('click', () => filters.requestSubmit());
    feedback.append(document.createTextNode(' '), retry);
    if (returnFocus && state.button.isConnected) state.button.focus({preventScroll: true});
  });

  // The board module owns feedback for these requests, including errors that
  // fire before/after afterRequest. Other SharedPost errors use the generic UI.
  for (const name of ['htmx:responseError', 'htmx:sendError', 'htmx:timeout']) {
    document.body.addEventListener(name, event => {
      if (optimisticRequests.has(event.detail.xhr)) event.preventDefault();
    });
  }
})();
