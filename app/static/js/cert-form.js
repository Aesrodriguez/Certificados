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

  /* ── Catálogo enviado por el servidor ── */
  var cat = document.getElementById('catalogo');
  function leerJSON(attr) {
    try { return JSON.parse(cat.getAttribute(attr) || '{}'); } catch (e) { return {}; }
  }
  var TIPOS        = cat ? leerJSON('data-tipos') : {};
  var SERVICIOS    = cat ? leerJSON('data-servicios') : {};
  var DESGLOSADOS  = cat ? leerJSON('data-desglosados') : {};
  var OTROS        = cat ? cat.getAttribute('data-otros') : 'OTROS';

  var TIPO_FACTURA   = 'CERTIFICADO DE GASTOS POR FACTURA';
  var TIPO_SERVICIOS = 'CERTIFICADO DE GASTOS POR SERVICIOS';

  var selEmpresa = document.getElementById('selectEmpresa');
  var selTipo    = document.getElementById('selectTipo');

  function opcion(value, text, selected) {
    var o = document.createElement('option');
    o.value = value;
    o.textContent = text;
    if (selected) o.selected = true;
    return o;
  }

  /* ── Tipo de documento según empresa ── */
  function llenarTipos() {
    if (!selTipo) return;
    var actual = selTipo.value || selTipo.getAttribute('data-actual') || '';
    selTipo.setAttribute('data-actual', '');
    var lista = TIPOS[selEmpresa.value] || [];
    selTipo.innerHTML = '';
    selTipo.appendChild(opcion('', '-- Seleccionar --', false));
    lista.forEach(function (t) { selTipo.appendChild(opcion(t, t, t === actual)); });
    if (actual && lista.indexOf(actual) === -1 && !selEmpresa.value) {
      selTipo.appendChild(opcion(actual, actual, true));  // valor antiguo / importado
    }
    if (lista.length === 1 && !selTipo.value) selTipo.value = lista[0];
    mostrarCamposTipo();
  }

  /* ── Campos visibles según el tipo ── */
  function mostrarCamposTipo() {
    var t = selTipo ? selTipo.value : '';
    var grupos = {
      gastos:     t === TIPO_FACTURA || t === TIPO_SERVICIOS,
      factura:    t === TIPO_FACTURA,
      servicios:  t === TIPO_SERVICIOS,
      elementos:  t.indexOf('ELEMENTOS') !== -1
    };
    document.querySelectorAll('[data-solo-tipo]').forEach(function (el) {
      el.hidden = !grupos[el.getAttribute('data-solo-tipo')];
    });
  }

  /* ── Servicios prestados ── */
  var container   = document.getElementById('svcsContainer');
  var emptyNote   = document.getElementById('svcsEmpty');
  var totalTxt    = document.getElementById('valorTotalTxt');
  var destinoTxt  = document.getElementById('destinoFinal');
  var btnAdd      = document.getElementById('btnAddSvc');

  function cop(n) { return '$ ' + (n || 0).toLocaleString('es-CO'); }

  function quitarTildes(s) {
    return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
  }

  function recalc() {
    if (!container) return;
    var rows = container.querySelectorAll('.svc-row');
    emptyNote.style.display = rows.length ? 'none' : '';
    var sum = 0, nombres = [];
    rows.forEach(function (row) {
      var v = parseInt(row.querySelector('.svc-val').value || '0', 10);
      if (!isNaN(v)) sum += v;
      nombres.push(quitarTildes(row.querySelector('.svc-sel').value));
    });
    totalTxt.textContent = cop(sum);
    var destino = '';
    if (nombres.some(function (n) { return n.indexOf('CREMACION') !== -1; })) {
      destino = '(Cremación – Destino Final)';
    } else if (nombres.some(function (n) { return n.indexOf('SERVICIO FUNERARIO') === 0; })) {
      destino = '(Inhumación – Destino Final)';
    }
    destinoTxt.textContent = destino;
  }

  function llenarServicios(sel, actual) {
    var lista = SERVICIOS[selEmpresa.value] || [];
    sel.innerHTML = '';
    sel.appendChild(opcion('', '-- Servicio --', false));
    lista.forEach(function (s) { sel.appendChild(opcion(s, s, s === actual)); });
    if (actual && lista.indexOf(actual) === -1) sel.appendChild(opcion(actual, actual, true));
  }

  function desglosa(servicio) {
    return (DESGLOSADOS[selEmpresa.value] || []).indexOf(servicio) !== -1;
  }

  function pintarDesglose(row) {
    var sel   = row.querySelector('.svc-sel');
    var desc  = row.querySelector('.svc-desc');
    var val   = parseInt(row.querySelector('.svc-val').value || '0', 10);
    var box   = row.querySelector('.svc-desglose');
    var esOtros = sel.value === OTROS;

    desc.parentElement.hidden = !esOtros;
    desc.required = esOtros;
    box.innerHTML = '';

    if (!sel.value) return;
    if (!desglosa(sel.value)) {
      box.textContent = 'No se desglosa.';
      return;
    }
    if (!val) {
      box.textContent = 'Ingresa el valor para ver el desglose.';
      return;
    }
    clearTimeout(row._t);
    row._t = setTimeout(function () {
      var url = '/certificates/api/lineas'
        + '?empresa=' + encodeURIComponent(selEmpresa.value)
        + '&nombre_servicio=' + encodeURIComponent(sel.value)
        + '&valor_total=' + val;
      fetch(url, { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (items) {
          box.innerHTML = '';
          var tbl = document.createElement('table');
          tbl.className = 'table table-sm table-borderless mb-0 small text-muted';
          (items || []).forEach(function (it) {
            var tr = document.createElement('tr');
            var a = document.createElement('td'); a.textContent = it.nombre;
            var b = document.createElement('td'); b.className = 'text-end text-nowrap';
            b.textContent = it.valor ? cop(it.valor) : '$ -';
            tr.appendChild(a); tr.appendChild(b); tbl.appendChild(tr);
          });
          box.appendChild(tbl);
        })
        .catch(function () { box.textContent = 'No se pudo calcular el desglose.'; });
    }, 350);
  }

  function addRow(item) {
    item = item || {};
    var row = document.createElement('div');
    row.className = 'svc-row border rounded p-2 mb-2';
    row.innerHTML =
      '<div class="row g-2 align-items-center">' +
        '<div class="col-md-5"><select class="form-select form-select-sm svc-sel" name="svc_servicio" required></select></div>' +
        '<div class="col-md-4"><input type="text" class="form-control form-control-sm svc-desc" name="svc_desc" maxlength="300" placeholder="Descripción del ítem"></div>' +
        '<div class="col"><input type="number" class="form-control form-control-sm svc-val" name="svc_valor" min="0" placeholder="Valor COP"></div>' +
        '<div class="col-auto"><button type="button" class="btn btn-sm btn-outline-danger svc-del" title="Eliminar"><i class="bi bi-trash"></i></button></div>' +
      '</div>' +
      '<div class="svc-desglose small text-muted mt-1"></div>';

    var sel = row.querySelector('.svc-sel');
    llenarServicios(sel, item.servicio || '');
    row.querySelector('.svc-desc').value = item.desc || '';
    row.querySelector('.svc-val').value  = item.valor || '';

    sel.addEventListener('change', function () { pintarDesglose(row); recalc(); });
    row.querySelector('.svc-val').addEventListener('input', function () { pintarDesglose(row); recalc(); });
    row.querySelector('.svc-del').addEventListener('click', function () { row.remove(); recalc(); });

    container.appendChild(row);
    pintarDesglose(row);
    recalc();
    return row;
  }

  if (selEmpresa) {
    selEmpresa.addEventListener('change', function () {
      llenarTipos();
      if (container) {
        container.querySelectorAll('.svc-row').forEach(function (row) {
          var sel = row.querySelector('.svc-sel');
          var lista = SERVICIOS[selEmpresa.value] || [];
          llenarServicios(sel, lista.indexOf(sel.value) !== -1 ? sel.value : '');
          pintarDesglose(row);
        });
        recalc();
      }
    });
  }
  if (selTipo) selTipo.addEventListener('change', mostrarCamposTipo);
  llenarTipos();

  if (container && btnAdd) {
    btnAdd.addEventListener('click', function () {
      if (!selEmpresa.value) {
        selEmpresa.classList.add('is-invalid');
        selEmpresa.focus();
        return;
      }
      addRow({}).querySelector('.svc-sel').focus();
    });
    try {
      var items = JSON.parse(container.getAttribute('data-initial') || '[]');
      if (Array.isArray(items)) items.forEach(addRow);
    } catch (e) { /* ignore parse errors */ }
    recalc();
  }

  /* ── Validación de fechas ──
     Cadena en orden: nacimiento → fallecimiento → servicio → solicitud.
     Cada fecha no puede ser futura ni anterior a la anterior de la cadena (si ambas están llenas). */
  var today = new Date();
  today.setHours(0, 0, 0, 0);

  var CADENA = [
    { id: 'fechaNacimiento',    nombre: 'nacimiento' },
    { id: 'fechaFallecimiento', nombre: 'fallecimiento', antes: 'La fecha de fallecimiento no puede ser anterior a la de nacimiento.' },
    { id: 'fechaServicio',      nombre: 'del servicio',  antes: 'La fecha del servicio no puede ser anterior a la de fallecimiento.' },
    { id: 'fechaSolicitud',     nombre: 'de solicitud',  antes: 'La fecha de solicitud no puede ser anterior a la del servicio.' }
  ].map(function (c) {
    c.el  = document.getElementById(c.id);
    c.err = c.el ? c.el.parentElement.querySelector('.invalid-feedback') : null;
    return c;
  }).filter(function (c) { return c.el; });

  function marcar(c, msg) {
    c.el.classList.add('is-invalid');
    if (c.err) { c.err.textContent = msg; c.err.style.display = 'block'; }
  }

  function limpiar(c) {
    c.el.classList.remove('is-invalid');
    if (c.err) c.err.style.display = 'none';
  }

  function validarFechaCadena(idx) {
    var c = CADENA[idx];
    var prev = idx > 0 ? CADENA[idx - 1] : null;
    if (prev) c.el.min = prev.el.value || '';
    if (!c.el.value) { limpiar(c); return true; }
    if (new Date(c.el.value + 'T00:00:00') > today) {
      marcar(c, 'La fecha ' + c.nombre + ' no puede ser futura.');
      return false;
    }
    if (prev && prev.el.value && c.el.value < prev.el.value) {
      marcar(c, c.antes);
      return false;
    }
    limpiar(c);
    return true;
  }

  function validarFechas(desde) {
    var ok = true;
    for (var k = desde || 0; k < CADENA.length; k++) {
      if (!validarFechaCadena(k)) ok = false;
    }
    return ok;
  }

  CADENA.forEach(function (c, idx) {
    if (idx > 0) c.el.min = CADENA[idx - 1].el.value || '';
    c.el.addEventListener('change', function () {
      validarFechaCadena(idx);
      // revalidar las siguientes que ya tengan valor (su mínimo cambió)
      for (var k = idx + 1; k < CADENA.length; k++) {
        if (CADENA[k].el.value) validarFechaCadena(k); else CADENA[k].el.min = CADENA[k - 1].el.value || '';
      }
    });
  });

  /* ── Validación general al enviar ── */
  var certForm = document.getElementById('certForm');
  if (!certForm) return;

  certForm.addEventListener('submit', function (e) {
    var ok = true;

    this.querySelectorAll('[required]').forEach(function (el) {
      if (el.closest('[hidden]')) return;
      if (!el.value.trim()) {
        el.classList.add('is-invalid');
        ok = false;
      } else {
        el.classList.remove('is-invalid');
      }
    });

    if (!validarFechas(0)) ok = false;

    if (!ok) {
      e.preventDefault();
      var first = document.querySelector('.is-invalid');
      if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
});
