// Printer calibration, kept in this browser.
//
// A printer that makes the 100 mm ruler come out at 98 mm gets a factor of
// 100 / 98; the server draws the page that much larger so the printer's own
// shrinking brings it back. The list of printers and the one last chosen live
// in localStorage, and the chosen factor travels with the form as `scale`.
(() => {
  const PRINTERS = "exactly-print.printers";
  const CHOSEN = "exactly-print.printer";
  // The same bounds the server enforces: a ruler between 80 and 125 mm.
  const MIN_MEASURED = 80;
  const MAX_MEASURED = 125;

  const form = document.getElementById("setup");
  const select = document.getElementById("printer");
  const scaleField = form.elements.scale;
  const removeButton = document.getElementById("printer-remove");
  const dialog = document.getElementById("calibrate");
  const calForm = document.getElementById("calibrate-form");
  const result = document.getElementById("calibrate-result");
  const problem = document.getElementById("calibrate-error");
  if (!form || !select || !dialog || !calForm) return;

  const read = (key) => {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  };
  const write = (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Private window or storage blocked: the calibration still works for this page.
    }
  };

  const loadPrinters = () => {
    try {
      const list = JSON.parse(read(PRINTERS) || "[]");
      if (!Array.isArray(list)) return [];
      return list.filter(
        (p) => p && typeof p.name === "string" && p.name.trim() && Number.isFinite(p.factor)
      );
    } catch {
      return [];
    }
  };
  let printers = loadPrinters();
  const savePrinters = () => write(PRINTERS, JSON.stringify(printers));
  const find = (name) => printers.find((p) => p.name === name);

  // How the printer behaves without a correction: mm printed per 100 mm asked.
  const printsAt = (factor) => (100 / factor).toFixed(1);

  const fillPrinterOptions = (target, chosen) => {
    target.replaceChildren();
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "None — print at 100%";
    target.append(none);
    for (const p of printers) {
      const option = document.createElement("option");
      option.value = p.name;
      option.textContent = `${p.name} — prints ${printsAt(p.factor)} mm per 100`;
      target.append(option);
    }
    target.value = find(chosen) ? chosen : "";
  };

  const applyChoice = () => {
    const chosen = find(select.value);
    scaleField.value = chosen ? String(chosen.factor) : "";
    removeButton.hidden = !chosen;
    write(CHOSEN, select.value);
  };

  fillPrinterOptions(select, read(CHOSEN) || "");
  applyChoice();
  // This runs at the target before htmx sees the event bubble to the form,
  // so the preview request already carries the new factor.
  select.addEventListener("change", applyChoice);

  removeButton.addEventListener("click", () => {
    const name = select.value;
    if (!name || !window.confirm(`Remove the calibration for "${name}"?`)) return;
    printers = printers.filter((p) => p.name !== name);
    savePrinters();
    fillPrinterOptions(select, "");
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });

  // The dialog.
  const fields = calForm.elements;
  const toMm = (value, unit) => value * (unit === "cm" ? 10 : 1);

  const parseMeasured = () => {
    const raw = fields.measured.value.trim().replace(",", ".");
    if (!raw) return null;
    const value = Number(raw);
    return Number.isFinite(value) && value > 0 ? toMm(value, fields.unit.value) : NaN;
  };

  // The new factor stacks on the one the measured page was printed with, so
  // a second round refines the first instead of throwing it away.
  const proposed = () => {
    const measured = parseMeasured();
    if (measured === null || Number.isNaN(measured)) return { measured, factor: null };
    const base = find(fields.base.value);
    const factor = (base ? base.factor : 1) * (100 / measured);
    return { measured, factor: Math.round(factor * 1e6) / 1e6 };
  };

  const describe = () => {
    fields.measured.placeholder = fields.unit.value === "cm" ? "9.85" : "98.5";
    problem.textContent = "";
    const { measured, factor } = proposed();
    if (factor === null) {
      result.textContent = "";
      return;
    }
    const equivalent = 100 / factor;
    if (equivalent < MIN_MEASURED || equivalent > MAX_MEASURED) {
      result.textContent = "";
      problem.textContent =
        `A ruler that measures ${measured.toFixed(1)} mm is off by more than a printer ` +
        'scales. Check that the page printed at 100% / "Actual size" on the right paper.';
      return;
    }
    result.textContent =
      `The page will be drawn at ×${factor.toFixed(3)}, so what came out as ` +
      `${measured.toFixed(1)} mm prints as 100 mm.`;
  };

  for (const name of ["measured", "unit", "base"]) {
    fields[name].addEventListener("input", describe);
    fields[name].addEventListener("change", describe);
  }

  document.getElementById("calibrate-open").addEventListener("click", () => {
    const chosen = find(select.value);
    fields.name.value = chosen ? chosen.name : "";
    fillPrinterOptions(fields.base, select.value);
    fields.measured.value = "";
    fields.unit.value = form.elements.unit.value;
    describe();
    dialog.showModal();
    fields.name.focus();
  });

  document.getElementById("calibrate-cancel").addEventListener("click", () => dialog.close());
  document.getElementById("calibrate-help").addEventListener("click", () => dialog.close());

  calForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const name = fields.name.value.trim();
    const { measured, factor } = proposed();
    if (!name) {
      problem.textContent = "Give the printer a name.";
      fields.name.focus();
      return;
    }
    if (factor === null) {
      problem.textContent =
        measured === null ? "Type what the ruler measured." : "That is not a length.";
      fields.measured.focus();
      return;
    }
    const equivalent = 100 / factor;
    if (equivalent < MIN_MEASURED || equivalent > MAX_MEASURED) {
      describe();
      return;
    }
    const entry = { name, factor, measured, savedAt: new Date().toISOString() };
    const index = printers.findIndex((p) => p.name === name);
    if (index === -1) printers.push(entry);
    else printers[index] = entry;
    savePrinters();
    fillPrinterOptions(select, name);
    dialog.close();
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
})();
