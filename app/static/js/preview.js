document.addEventListener('DOMContentLoaded', function () {
  var btnPrint = document.getElementById('btnPrint');
  if (btnPrint) {
    btnPrint.addEventListener('click', function () {
      window.print();
    });
  }
});
