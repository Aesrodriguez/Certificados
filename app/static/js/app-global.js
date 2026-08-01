(function () {
  var loader = document.getElementById('globalLoader');

  function showLoader() { if (loader) loader.style.display = 'flex'; }
  function hideLoader() { if (loader) loader.style.display = 'none'; }

  window.addEventListener('pageshow', hideLoader);

  document.addEventListener('submit', function (e) {
    setTimeout(function () {
      if (!e.defaultPrevented) showLoader();
    }, 0);
  });

  document.addEventListener('click', function (e) {
    var link = e.target.closest('a[href]');
    if (!link) return;
    if (e.ctrlKey || e.metaKey || e.shiftKey) return;
    var href = link.getAttribute('href') || '';
    if (!href || href.startsWith('#') || href.startsWith('javascript')) return;
    if (link.target === '_blank') return;
    if (link.hasAttribute('data-bs-toggle') || link.hasAttribute('data-bs-dismiss')) return;

    showLoader();
    if (href.indexOf('/pdf') !== -1) {
      setTimeout(hideLoader, 3000);
    }
  });

  var toggle  = document.getElementById('sidebarToggle');
  var sidebar = document.getElementById('appSidebar');
  var overlay = document.getElementById('sidebarOverlay');
  if (toggle && sidebar && overlay) {
    toggle.addEventListener('click', function () {
      sidebar.classList.toggle('open');
      overlay.classList.toggle('open');
    });
    overlay.addEventListener('click', function () {
      sidebar.classList.remove('open');
      overlay.classList.remove('open');
    });
  }
})();
