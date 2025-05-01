class StyledCard extends HTMLElement {
  constructor() {
    super();
    const shadow = this.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
          :host {
              display: block;
              background-color: #002923;
              border-radius: 8px;
              color: white;
              width: 400px;
              height: 100px;
              padding: 16px;
              box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
              font-family: Arial, sans-serif;
              margin: 15px;
              align-content: center;
          }

          .header {
              font-size: 1.5em;
              text-align: center;
              margin-bottom: 15px;
          }

          .value {
              font-size: 2.5em;
              font-weight: bold;
              text-align: center;
              color: white;
          }

          .description {
              font-size: 1em;
              color: #CCCCCC;
              text-align: left;
              margin-top: 15px;
          }
      `;

    const container = document.createElement("div");
    container.innerHTML = `
          <div class="header">
              <slot name="header">Default Header</slot>
          </div>
          <div class="value">
              <slot name="value">0.0</slot>
          </div>
          <div class="description">
              <slot name="description">Default Description</slot>
          </div>
      `;

    shadow.appendChild(style);
    shadow.appendChild(container);
  }
}

customElements.define("styled-card", StyledCard);

class RecommendationItem extends HTMLElement {
  constructor() {
    super();
    const shadow = this.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      @import url('https://fonts.googleapis.com/icon?family=Material+Icons');

      :host {
        display: block;
        margin-bottom: 10px;
      }

      .recommendation-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 15px;
        border: 2px solid rgb(0, 128, 0);
        border-radius: 10px;
        background-color: black;
        color: white;
      }

      .icon {
        font-family: 'Material Icons';
        font-size: 3rem;
        color: rgb(0, 128, 0);
        margin-right: 10px;
      }

      .title {
        flex-grow: 1;
        font-size: 1.5rem;
        color: white;
      }

      .score {
        font-size: 1.5rem;
        color: white;
        margin-right: 10px;
      }

      .action {
        font-family: 'Material Icons';
        font-size: 3rem;
        cursor: pointer;
        color: rgb(0, 128, 0);
      }
    `;

    const container = document.createElement("div");
    container.className = "recommendation-item";
    container.innerHTML = `
      <span class="icon">help</span>
      <span class="title"></span>
      <span class="score"></span>
      <span class="action">arrow_downward</span>
    `;

    shadow.appendChild(style);
    shadow.appendChild(container);
  }

  connectedCallback() {
    const shadow = this.shadowRoot;

    shadow.querySelector(".icon").textContent =
      this.getAttribute("icon") || "help";
    shadow.querySelector(".title").textContent =
      this.getAttribute("title") || "Title";
    shadow.querySelector(".score").textContent =
      this.getAttribute("score") || "Score";
  }
}

customElements.define("recommendation-item", RecommendationItem);

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
