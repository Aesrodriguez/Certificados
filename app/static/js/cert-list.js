var statusLabels = {draft:'Borrador', pending:'Pendiente', approved:'Aprobado', rejected:'Rechazado'};
var statusColors  = {draft:'badge-draft', pending:'badge-pending', approved:'badge-approved', rejected:'badge-rejected'};

function setText(id, val) {
  var el = document.getElementById(id);
  if (el) el.textContent = val !== undefined && val !== null ? val : '';
}
function setHref(id, val) {
  var el = document.getElementById(id);
  if (el) el.href = val;
}
function setDisplay(id, val) {
  var el = document.getElementById(id);
  if (el) el.style.display = val;
}

function resetModal() {
  setText('mFallecido',      'Cargando…');
  setText('mFecha',          '');
  setText('mTipo',           '—');
  setText('mEmpresa',        '—');
  setText('mFallecidoNombre','');
  setText('mFallecidoDoc',   '');
  setText('mFallecidoFecha', '');
  setText('mAfiliacion',     '');
  setText('mClienteNombre',  '');
  setText('mClienteDoc',     '');
  setText('mClienteEmail',   '');
  setText('mContrato',       '—');
  setText('mRecibo',         '—');
  setText('mAviso',          '—');
  setText('mObs',            '');
  setDisplay('mObsWrap',     'none');
  var badge = document.getElementById('mStatusBadge');
  if (badge) { badge.className = ''; badge.textContent = ''; }
  var editLink = document.getElementById('mEditLink');
  if (editLink) editLink.style.display = 'none';
}

function verCert(id) {
  resetModal();

  fetch('/certificates/' + id + '/quick')
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (d) {
      var s = d.status || '';
      setText('mFallecido',       d.fallecido  || '(sin nombre)');
      setText('mFecha',           d.fecha      || '');
      setText('mTipo',            d.tipo       || '—');
      setText('mEmpresa',         d.empresa    || '—');
      setText('mFallecidoNombre', d.fallecido  || '—');
      setText('mFallecidoDoc',    d.fdoc       || '—');
      setText('mFallecidoFecha',  d.ffecha     || '—');
      setText('mAfiliacion',      d.afiliacion || '—');
      setText('mClienteNombre',   d.cliente    || '—');
      setText('mClienteDoc',      d.cdoc       || '—');
      setText('mClienteEmail',    d.cemail     || '—');
      setText('mContrato',        d.contrato   || '—');
      setText('mRecibo',          d.recibo     || '—');
      setText('mAviso',           d.aviso      || '—');
      setText('mObs',             d.obs        || '');
      setDisplay('mObsWrap', d.obs ? 'block' : 'none');

      var badge = document.getElementById('mStatusBadge');
      if (badge) {
        badge.className   = 'badge-status ' + (statusColors[s] || '');
        badge.textContent = statusLabels[s] || s;
      }

      setHref('mPreviewLink', '/certificates/' + id + '/preview');

      var editLink = document.getElementById('mEditLink');
      if (editLink) {
        var canEdit = (s === 'draft' || s === 'rejected');
        editLink.href          = '/certificates/' + id + '/edit';
        editLink.style.display = canEdit ? 'inline-flex' : 'none';
      }
    })
    .catch(function (err) {
      setText('mFallecido', 'Error al cargar (' + (err.message || err) + ')');
    });
}

document.addEventListener('DOMContentLoaded', function () {
  var certModalEl = document.getElementById('certModal');
  if (!certModalEl) return;
  certModalEl.addEventListener('show.bs.modal', function (event) {
    var btn = event.relatedTarget;
    var id  = btn ? btn.getAttribute('data-cert-id') : null;
    if (id) verCert(id);
  });
});
