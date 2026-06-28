  // Upload-preparation validation errors are stored by experiment.js before the
  // redirect and rendered once on the preprocess page.
  document.addEventListener("DOMContentLoaded", () => {
    const raw = sessionStorage.getItem("dvErrors");
    if (!raw) return;
    let lines = [];
    try {
      lines = JSON.parse(raw) || [];
    } catch (err) {
      sessionStorage.removeItem("dvErrors");
      return;
    }
    sessionStorage.removeItem("dvErrors");
    if (!Array.isArray(lines) || lines.length === 0) return;

    let container = document.querySelector(".message-container.dv-overlay");
    if (!container) {
      container = document.createElement("div");
      container.className = "message-container dv-overlay";
      document.body.appendChild(container);
    }

    const key = lines.filter((line) => line).join("\n").trim() || "dv-errors";
    const existing = Array.from(
      container.querySelectorAll(".message.dv-error")
    ).some((msg) => msg.dataset.key === key);
    if (existing) return;

    const formattedLines = lines
      .map((line) => {
        if (!line) {
          return '<div class="dv-error-separator"></div>';
        }
        const isHeader = line.startsWith("Could not process");
        const cleanedLine = isHeader
          ? line
          : line
              .replace(/\s*\(expected\s*\d+\s*layers?\)/i, "")
              .replace(/\s*\(expected\s*\d+\s*\)/i, "");
        const lineClass = isHeader ? "dv-error-line is-header" : "dv-error-line";
        return `<div class="${lineClass}">${cleanedLine}</div>`;
      })
      .join("");
    const hasSections = lines.some((line) => !line);
    const headerLine = hasSections
      ? '<div class="dv-error-section-title">Input checks to review:</div><div class="dv-error-separator"></div>'
      : "";

    const message = document.createElement("div");
    message.className = "message dv-error";
    message.dataset.key = key;
    message.innerHTML = `${headerLine}${formattedLines}`;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "message-close";
    close.setAttribute("aria-label", "Dismiss");
    close.innerHTML = "&times;";
    close.addEventListener("click", () => message.remove());
    message.appendChild(close);
    container.prepend(message);
    setTimeout(() => message.remove(), 60000);
  });
