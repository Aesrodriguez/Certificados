document.addEventListener('DOMContentLoaded', function () {
  var sw  = document.getElementById('emailEnabled');
  var lbl = sw ? sw.nextElementSibling : null;
  if (!sw || !lbl) return;
  sw.addEventListener('change', function () {
    lbl.innerHTML = this.checked
      ? '<span class="text-success">Activo</span>'
      : '<span class="text-secondary">Inactivo</span>';
  });
});
