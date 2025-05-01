document.addEventListener("DOMContentLoaded", () => {
  fetch("/header")
    .then((response) => response.text())
    .then((html) => {
      document.body.insertAdjacentHTML("afterbegin", html);
    });
});

function showAnalyzeButton() {
  const button = document.getElementById("analyze-button");
  const fileInput = document.getElementById("file-input");
  const fileNameDisplay = document.getElementById("file-name");

  if (fileInput.files.length > 0) {
    button.style.display = "block";
    fileNameDisplay.textContent = fileInput.files[0].name;
  } else {
    fileNameDisplay.textContent =
      "Drag your HTML file here or click to upload and watch the magic happen!";
    button.style.display = "none";
  }
}

const uploadBox = document.getElementById("upload-box");
const fileInput = document.getElementById("file-input");

uploadBox.addEventListener("dragover", (event) => {
  event.preventDefault();
  uploadBox.classList.add("drag-over");
});

uploadBox.addEventListener("dragleave", () => {
  uploadBox.classList.remove("drag-over");
});

uploadBox.addEventListener("drop", (event) => {
  event.preventDefault();
  uploadBox.classList.remove("drag-over");
  const files = event.dataTransfer.files;
  if (files.length > 0) {
    fileInput.files = files;
    showAnalyzeButton();
  }
});
