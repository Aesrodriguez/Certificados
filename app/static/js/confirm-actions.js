(function () {
  var pendingForm = null;
  var modalEl = null;
  var bsModal = null;

  function buildModal() {
    if (modalEl) return;
    modalEl = document.createElement('div');
    modalEl.className = 'modal fade';
    modalEl.tabIndex = -1;
    modalEl.innerHTML =
      '<div class="modal-dialog modal-dialog-centered modal-sm">' +
        '<div class="modal-content">' +
          '<div class="modal-body text-center py-4" id="_caBody" style="font-size:14.5px; line-height:1.5;"></div>' +
          '<div class="modal-footer justify-content-center border-0 pt-0 pb-3">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm px-4" data-bs-dismiss="modal">Cancelar</button>' +
            '<button type="button" class="btn btn-danger btn-sm px-4" id="_caOk">Confirmar</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(modalEl);

    document.getElementById('_caOk').addEventListener('click', function () {
      bsModal.hide();
      if (pendingForm) {
        var f = pendingForm;
        pendingForm = null;
        f.dataset.caConfirmed = '1';
        f.requestSubmit ? f.requestSubmit() : f.submit();
      }
    });
  }

  document.addEventListener('submit', function (event) {
    var form = event.target;

    if (form.dataset.caConfirmed) {
      delete form.dataset.caConfirmed;
      return;
    }

    var message = form.dataset.confirm;
    if (!message) return;

    event.preventDefault();
    pendingForm = form;

    buildModal();
    document.getElementById('_caBody').textContent = message;

    if (!bsModal) {
      bsModal = new bootstrap.Modal(modalEl, { keyboard: true });
    }
    bsModal.show();
  });
})();
