function showAnalyzeButton() {
  const button = document.getElementById("analyze-button");
  const fileInput = document.getElementById("file-input");
  const fileNameDisplay = document.getElementById("file-name");
  const emptyLabel =
    fileNameDisplay?.dataset.emptyLabel ||
    "Arrastra aquí tu archivo HTML o ZIP, o haz clic para seleccionarlo.";

  if (!button || !fileInput || !fileNameDisplay) {
    return;
  }

  if (fileInput.files.length > 0) {
    button.style.display = "block";
    fileNameDisplay.textContent = fileInput.files[0].name;
  } else {
    fileNameDisplay.textContent = emptyLabel;
    button.style.display = "none";
  }
}

function initUploadPage() {
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

function formatMetricValue(value, digits = 2) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function formatAdaptiveMetric(value) {
  const absolute = Math.abs(value);
  if (absolute >= 100) {
    return formatMetricValue(value, 1);
  }
  if (absolute >= 10) {
    return formatMetricValue(value, 2);
  }
  if (absolute >= 1) {
    return formatMetricValue(value, 3);
  }
  return formatMetricValue(value, 4);
}

function formatEnergyMetric(wh) {
  if (Math.abs(wh) >= 1000) {
    return {
      value: formatAdaptiveMetric(wh / 1000),
      unit: "kWh consumed",
    };
  }

  return {
    value: formatAdaptiveMetric(wh),
    unit: "Wh consumed",
  };
}

function clampPositiveInteger(rawValue, fallback) {
  const parsed = Number.parseInt(rawValue, 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return fallback;
  }
  return parsed;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = value;
  }
}

function updateImpact() {
  const page = document.querySelector('main[data-page="results"]');
  const userInput = document.getElementById("user_count");
  const hoursInput = document.getElementById("usage_hours");

  if (!page || !userInput || !hoursInput) {
    return;
  }

  const users = clampPositiveInteger(userInput.value, 100);
  const hours = clampPositiveInteger(hoursInput.value, 24);
  userInput.value = String(users);
  hoursInput.value = String(hours);

  const energyWh = Number.parseFloat(page.dataset.energyWh || "0") || 0;
  const carbonPerUse = Number.parseFloat(page.dataset.carbonFootprint || "0") || 0;
  const environmentalPerUse =
    Number.parseFloat(page.dataset.environmentalCarbonFootprint || "0") || 0;

  const totalEnergy = energyWh * users * hours;
  const totalCarbon = carbonPerUse * users * hours;
  const totalEnvironmental = environmentalPerUse * users * hours;
  const reduction = totalCarbon - totalEnvironmental;
  const reductionAbsolute = Math.abs(reduction);
  const improvementPercent =
    totalCarbon !== 0 ? (reduction / totalCarbon) * 100 : 0;
  const formattedEnergy = formatEnergyMetric(totalEnergy);

  const lead = reduction >= 0 ? "could emit" : "currently emits";
  const tail = reduction >= 0 ? "kg less CO₂eq" : "kg more CO₂eq";
  const pill =
    reduction >= 0
      ? `↓ ${formatAdaptiveMetric(Math.abs(improvementPercent))}% improvement potential`
      : `↑ ${formatAdaptiveMetric(Math.abs(improvementPercent))}% footprint increase`;
  const support =
    reduction >= 0
      ? "The optimized variant reduces carbon mostly by redistributing luminance, lowering bright structural surfaces, and cleaning up emphasis."
      : "In this run the optimized variant slightly increases the footprint, so the next pass should focus on lowering bright area before tuning accents.";

  setText("heroReductionLead", lead);
  setText("heroReductionValue", formatAdaptiveMetric(reductionAbsolute));
  setText("heroReductionTail", tail);
  setText("heroImprovementPill", pill);
  setText("heroSupportCopy", support);
  setText("summaryCarbonValue", formatAdaptiveMetric(totalCarbon));
  setText("summaryCarbonUnit", "kg CO₂eq generated");
  setText("summaryEnergyValue", formattedEnergy.value);
  setText("summaryEnergyUnit", formattedEnergy.unit);
  setText("summaryUsers", String(users));
  setText("summaryHours", String(hours));
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
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  const copied = document.execCommand && document.execCommand("copy");
  document.body.removeChild(textarea);

  if (!copied) {
    throw new Error("Clipboard copy failed");
  }
}

function setPaletteCopyFeedback(button, copiedText) {
  const status = document.getElementById("paletteCopyStatus");
  const originalTitle = button.getAttribute("aria-label") || "";
  const originalTooltip = button.getAttribute("title") || copiedText;

  if (status) {
    status.textContent = `Color ${copiedText} copiado al portapapeles.`;
  }

  button.classList.add("copied");
  button.setAttribute("title", `Copiado ${copiedText}`);
  button.setAttribute("aria-label", `Copiado ${copiedText}`);

  window.clearTimeout(button._copyTimer);
  button._copyTimer = window.setTimeout(() => {
    button.classList.remove("copied");
    button.setAttribute("title", originalTooltip);
    button.setAttribute("aria-label", originalTitle);
  }, 1400);
}

function initPaletteSwatches() {
  const swatches = document.querySelectorAll(".swatch");
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
        button.setAttribute("title", "No se pudo copiar");
      }
    });
  });
}

function initReportPage() {
  const page = document.querySelector('main[data-page="results"]');
  if (!page) {
    return;
  }

  const updateButton = document.getElementById("update-impact-button");
  if (updateButton) {
    updateButton.addEventListener("click", updateImpact);
  }

  updateImpact();
  initPaletteSwatches();
}

document.addEventListener("DOMContentLoaded", () => {
  initUploadPage();
  initReportPage();
});
