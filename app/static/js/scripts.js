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

  if (!button || !fileInput || !fileNameDisplay) {
    return;
  }

  if (fileInput.files.length > 0) {
    button.style.display = "block";
    fileNameDisplay.textContent = fileInput.files[0].name;
  } else {
    fileNameDisplay.textContent =
      "Drag your HTML file here or click to upload and watch the magic happen!";
    button.style.display = "none";
  }
}

function initializeUploadPage() {
  const uploadBox = document.getElementById("upload-box");
  const fileInput = document.getElementById("file-input");
  if (!uploadBox || !fileInput) {
    return;
  }

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
}

function updateImpact() {
  const page = document.querySelector(".results-page");
  const userInput = document.getElementById("user_count");
  const hoursInput = document.getElementById("usage_hours");

  if (!page || !userInput || !hoursInput) {
    return;
  }

  const users = parseInt(userInput.value, 10);
  const hours = parseInt(hoursInput.value, 10);
  const energyWh = parseFloat(page.dataset.energyWh || "0");
  const co2eqPerUse = parseFloat(page.dataset.carbonFootprint || "0");
  const environmentalCo2eqPerUse = parseFloat(
    page.dataset.environmentalCarbonFootprint || "0"
  );

  const totalEnergy = energyWh * users * hours;
  const totalCo2eq = co2eqPerUse * users * hours;
  const totalEnvironmentalCo2eq = environmentalCo2eqPerUse * users * hours;
  const reductionCo2eq = totalCo2eq - totalEnvironmentalCo2eq;

  document
    .getElementById("energy_card")
    ?.querySelector('span[slot="value"]')
    ?.replaceChildren(document.createTextNode(`${totalEnergy.toFixed(2)} Wh`));
  document
    .getElementById("carbon_card")
    ?.querySelector('span[slot="value"]')
    ?.replaceChildren(document.createTextNode(`${totalCo2eq.toFixed(4)} kg CO₂eq`));
  document
    .getElementById("reduction_card")
    ?.querySelector('span[slot="value"]')
    ?.replaceChildren(document.createTextNode(`${reductionCo2eq.toFixed(4)} kg CO₂eq`));

  const setText = (id, value) => {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  };

  setText("e-users", String(users));
  setText("e-hours", String(hours));
  setText("e-total", totalEnergy.toFixed(2));
  setText("c-e", totalEnergy.toFixed(2));
  setText("c-total", totalCo2eq.toFixed(4));
  setText("a-orig", totalCo2eq.toFixed(4));
  setText("a-environmental", totalEnvironmentalCo2eq.toFixed(4));
  setText("a-total", reductionCo2eq.toFixed(4));
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

function setPaletteCopyFeedback(button, copiedText) {
  const status = document.getElementById("paletteCopyStatus");
  const icon = button.querySelector(".tonal-swatch-icon");
  const originalMessage = button.dataset.copyColor || copiedText;

  if (status) {
    status.textContent = `Color ${copiedText} copiado al portapapeles.`;
  }

  button.classList.add("copied");
  button.dataset.copyMessage = `Copiado ${copiedText}`;
  button.setAttribute("title", `Copiado ${copiedText}`);
  if (icon) {
    icon.textContent = "check";
  }

  window.clearTimeout(button._copyTimer);
  button._copyTimer = window.setTimeout(() => {
    button.classList.remove("copied");
    button.dataset.copyMessage = originalMessage;
    button.setAttribute(
      "title",
      `${button.dataset.copyLabel || "Color"} · ${copiedText} · Click para copiar`
    );
    if (icon) {
      icon.textContent = "eco";
    }
  }, 1400);
}

function initializePaletteSwatches() {
  const swatches = document.querySelectorAll(".tonal-swatch-button");
  if (!swatches.length) {
    return;
  }

  swatches.forEach((button) => {
    button.addEventListener("click", async () => {
      const copiedText = button.dataset.copyColor;
      if (!copiedText) {
        return;
      }

      try {
        await copyTextToClipboard(copiedText);
        setPaletteCopyFeedback(button, copiedText);
      } catch (error) {
        button.dataset.copyMessage = "No se pudo copiar";
      }
    });
  });
}

function initializeResultsPage() {
  const page = document.querySelector(".results-page");
  if (!page) {
    return;
  }

  const updateButton = document.getElementById("update-impact-button");
  if (updateButton) {
    updateButton.addEventListener("click", updateImpact);
  }
  updateImpact();

  const btns = document.querySelectorAll(".tab-btn");
  const img = document.getElementById("previewImage");
  const srcOriginal = page.dataset.previewOriginal;
  const srcEnvironmental = page.dataset.previewEnvironmental;

  if (btns.length && img && srcOriginal && srcEnvironmental) {
    btns.forEach((btn) => {
      btn.addEventListener("click", () => {
        btns.forEach((item) => item.classList.remove("active"));
        btn.classList.add("active");

        const target = btn.getAttribute("data-target");
        img.src = target === "environmental" ? srcEnvironmental : srcOriginal;
      });
    });
  }

  initializePaletteSwatches();
}

document.addEventListener("DOMContentLoaded", initializeResultsPage);
document.addEventListener("DOMContentLoaded", initializeUploadPage);
