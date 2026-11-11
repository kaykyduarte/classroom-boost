(() => {
  const toggle = document.querySelector('.menu-toggle');
  const sidebar = document.getElementById('sidebar');
  if (!toggle || !sidebar) return;

  const mobileQuery = window.matchMedia('(max-width: 760px)');
  if (mobileQuery.matches) toggle.setAttribute('aria-expanded', 'false');

  toggle.addEventListener('click', () => {
    if (mobileQuery.matches) {
      const opened = sidebar.classList.toggle('mobile-open');
      toggle.setAttribute('aria-expanded', String(opened));
    } else {
      document.body.classList.toggle('sidebar-collapsed');
      toggle.setAttribute('aria-expanded', String(!document.body.classList.contains('sidebar-collapsed')));
    }
  });

  document.addEventListener('click', (event) => {
    if (mobileQuery.matches && sidebar.classList.contains('mobile-open') &&
        !sidebar.contains(event.target) && !toggle.contains(event.target)) {
      sidebar.classList.remove('mobile-open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });

  mobileQuery.addEventListener('change', (event) => {
    sidebar.classList.remove('mobile-open');
    if (event.matches) {
      document.body.classList.remove('sidebar-collapsed');
      toggle.setAttribute('aria-expanded', 'false');
    } else {
      toggle.setAttribute('aria-expanded', String(!document.body.classList.contains('sidebar-collapsed')));
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('mobile-open')) {
      sidebar.classList.remove('mobile-open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });
})();
