document.addEventListener('DOMContentLoaded', function () {

  /* ── Solo dígitos en campos numéricos ── */
  document.querySelectorAll('.solo-nums').forEach(function (el) {
    el.addEventListener('input', function () {
      var pos  = this.selectionStart;
      var prev = this.value;
      this.value = prev.replace(/\D/g, '');
      if (this.value.length < prev.length) {
        this.setSelectionRange(pos - 1, pos - 1);
      }
    });
    el.addEventListener('keydown', function (e) {
      var allowed = ['Backspace','Delete','ArrowLeft','ArrowRight','ArrowUp','ArrowDown',
                     'Tab','Enter','Home','End'];
      if (allowed.indexOf(e.key) !== -1) return;
      if (e.ctrlKey || e.metaKey) return;
      if (!/^\d$/.test(e.key)) e.preventDefault();
    });
  });

  /* ── Filtrar servicios según empresa seleccionada ── */
  var grpRecordar = document.querySelector('.opts-recordar');
  var grpPyf      = document.querySelector('.opts-pyf');
  var selServicio = document.getElementById('selectServicio');
  var selEmpresa  = document.getElementById('selectEmpresa');

  if (selEmpresa && selServicio && grpRecordar && grpPyf) {
    function filtrarServicios() {
      var emp = selEmpresa.value;
      grpRecordar.style.display = (emp === '' || emp === 'RECORDAR')              ? '' : 'none';
      grpPyf.style.display      = (emp === '' || emp === 'PARQUES Y FUNERARIAS')  ? '' : 'none';

      var opt = selServicio.options[selServicio.selectedIndex];
      if (opt && opt.value !== '') {
        var cls = opt.className;
        if ((emp === 'RECORDAR'              && cls === 'opt-pyf') ||
            (emp === 'PARQUES Y FUNERARIAS'  && cls === 'opt-recordar')) {
          selServicio.value = '';
        }
      }
    }
    selEmpresa.addEventListener('change', filtrarServicios);
    filtrarServicios();
  }

  /* ── Validación de fechas ── */
  var today = new Date();
  today.setHours(0, 0, 0, 0);

  function validarFecha(inputEl, errEl) {
    if (!inputEl || !inputEl.value) return true;
    var d = new Date(inputEl.value + 'T00:00:00');
    if (d > today) {
      inputEl.classList.add('is-invalid');
      if (errEl) errEl.style.display = 'block';
      return false;
    }
    inputEl.classList.remove('is-invalid');
    inputEl.classList.add('is-valid');
    if (errEl) errEl.style.display = 'none';
    return true;
  }

  var fechaNac  = document.getElementById('fechaNacimiento');
  var fechaFall = document.getElementById('fechaFallecimiento');
  var errNac    = document.getElementById('errNacimiento');
  var errFall   = document.getElementById('errFallecimiento');

  if (fechaNac)  fechaNac.addEventListener('change',  function () { validarFecha(fechaNac,  errNac);  });
  if (fechaFall) fechaFall.addEventListener('change', function () { validarFecha(fechaFall, errFall); });

  /* ── Servicios dinámicos ── */
  var container  = document.getElementById('svcsContainer');
  var emptyNote  = document.getElementById('svcsEmpty');
  var valorTotal = document.getElementById('valorTotal');
  var btnAdd     = document.getElementById('btnAddSvc');

  if (container && btnAdd) {

    function recalcTotal() {
      var rows = container.querySelectorAll('.svc-row');
      emptyNote.style.display = rows.length === 0 ? '' : 'none';
      if (rows.length === 0) return;

      var sum = 0;
      rows.forEach(function (row) {
        var v = parseInt(row.querySelector('.svc-val').value || '0', 10);
        if (!isNaN(v)) sum += v;
      });
      if (valorTotal) valorTotal.value = sum > 0 ? sum : '';
    }

    function addRow(nombre, valor) {
      var idx = container.querySelectorAll('.svc-row').length;
      var div = document.createElement('div');
      div.className = 'svc-row row g-2 mb-2 align-items-center';
      div.innerHTML =
        '<div class="col">' +
          '<input type="text" class="form-control form-control-sm svc-nom" name="svc_nombre" ' +
                 'placeholder="Nombre del ítem" value="' + (nombre || '').replace(/"/g, '&quot;') + '" required>' +
        '</div>' +
        '<div class="col-md-3">' +
          '<input type="number" class="form-control form-control-sm svc-val" name="svc_valor" ' +
                 'placeholder="Valor COP" min="0" value="' + (valor || '') + '">' +
        '</div>' +
        '<div class="col-auto">' +
          '<button type="button" class="btn btn-sm btn-outline-danger svc-del" title="Eliminar">' +
            '<i class="bi bi-trash"></i>' +
          '</button>' +
        '</div>';

      div.querySelector('.svc-del').addEventListener('click', function () {
        div.remove();
        recalcTotal();
      });
      div.querySelector('.svc-val').addEventListener('input', recalcTotal);

      container.appendChild(div);
      recalcTotal();
      div.querySelector('.svc-nom').focus();
    }

    btnAdd.addEventListener('click', function () { addRow('', ''); });

    /* Initialise from server-side data attribute */
    var raw = container.getAttribute('data-initial');
    if (raw) {
      try {
        var items = JSON.parse(raw);
        if (Array.isArray(items)) {
          items.forEach(function (item) { addRow(item.nombre, item.valor); });
        }
      } catch (e) { /* ignore parse errors */ }
    }

    recalcTotal();
  }

  /* ── Validación general al enviar ── */
  var certForm = document.getElementById('certForm');
  if (!certForm) return;

  certForm.addEventListener('submit', function (e) {
    var ok = true;

    this.querySelectorAll('[required]').forEach(function (el) {
      if (!el.value.trim()) {
        el.classList.add('is-invalid');
        ok = false;
      } else {
        el.classList.remove('is-invalid');
      }
    });

    if (!validarFecha(fechaNac,  errNac))  ok = false;
    if (!validarFecha(fechaFall, errFall)) ok = false;

    if (fechaFall && !fechaFall.value) {
      fechaFall.classList.add('is-invalid');
      if (errFall) {
        errFall.textContent  = 'La fecha de fallecimiento es obligatoria.';
        errFall.style.display = 'block';
      }
      ok = false;
    }

    if (!ok) {
      e.preventDefault();
      var first = document.querySelector('.is-invalid');
      if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
});
