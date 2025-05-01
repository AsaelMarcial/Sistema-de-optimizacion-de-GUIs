document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("form");
  const fileInput = document.querySelector("input[type='file']");

  form.addEventListener("submit", function (event) {
    // Validar si el usuario seleccionó un archivo
    if (!fileInput.files.length) {
      event.preventDefault();
      alert("Por favor, selecciona un archivo antes de enviar.");
    }
  });
});
