document.addEventListener('DOMContentLoaded', function () {
  var btnPrint = document.getElementById('btnPrint');
  if (btnPrint) {
    btnPrint.addEventListener('click', function () {
      window.print();
    });
  }

  // El certificado debe quedar en una sola hoja carta. Si el contenido es más alto
  // que la hoja (muchos servicios), se reduce el tamaño de letra poco a poco hasta
  // que quepa. Todos los textos están en em, así que escalan juntos.
  var page = document.querySelector('.page');
  var content = document.querySelector('.cert-content');
  if (!page || !content) return;

  function ajustar() {
    var base = 11; // pt
    var minimo = 7.5;
    content.style.fontSize = base + 'pt';
    var tam = base;
    while (content.scrollHeight > page.clientHeight + 1 && tam > minimo) {
      tam -= 0.25;
      content.style.fontSize = tam + 'pt';
    }
  }

  ajustar();
  // Las imágenes (firma, sello) cambian la altura cuando terminan de cargar.
  window.addEventListener('load', ajustar);
  window.addEventListener('beforeprint', ajustar);
});
