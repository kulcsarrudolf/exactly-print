// Printer calibration, kept in this browser.
//
// A printer that makes the bottom 100 mm ruler come out at 98 mm gets a
// factor of 100 / 98 across, and the left ruler gives one down; the server
// draws the page that much larger so the printer's own shrinking brings it
// back. The list of printers and the one last chosen live in localStorage,
// and the chosen factors travel with the form as `scale_x` and `scale_y`.
(() => {
  const PRINTERS = "exactly-print.printers";
  const CHOSEN = "exactly-print.printer";
  // The same bounds the server enforces: a ruler between 80 and 125 mm.
  const MIN_MEASURED = 80;
  const MAX_MEASURED = 125;

  const form = document.getElementById("setup");
  const select = document.getElementById("printer");
  const removeButton = document.getElementById("printer-remove");
  const dialog = document.getElementById("calibrate");
  const calForm = document.getElementById("calibrate-form");
  const result = document.getElementById("calibrate-result");
  const problem = document.getElementById("calibrate-error");
  if (!form || !select || !dialog || !calForm) return;
  const scaleX = form.elements.scale_x;
  const scaleY = form.elements.scale_y;

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

  // Entries saved before the left ruler existed carry one `factor`; it
  // stands for both directions until the printer is calibrated again.
  const upgrade = (p) => {
    if (!p || typeof p.name !== "string" || !p.name.trim()) return null;
    const x = Number.isFinite(p.factorX) ? p.factorX : p.factor;
    const y = Number.isFinite(p.factorY) ? p.factorY : x;
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    return { ...p, factorX: x, factorY: y };
  };
  const loadPrinters = () => {
    try {
      const list = JSON.parse(read(PRINTERS) || "[]");
      return Array.isArray(list) ? list.map(upgrade).filter(Boolean) : [];
    } catch {
      return [];
    }
  };
  let printers = loadPrinters();
  const savePrinters = () => write(PRINTERS, JSON.stringify(printers));
  const find = (name) => printers.find((p) => p.name === name);

  // How the printer behaves without a correction: mm printed per 100 mm asked.
  const printsAt = (p) => {
    const x = (100 / p.factorX).toFixed(1);
    const y = (100 / p.factorY).toFixed(1);
    return x === y ? `${x} mm per 100` : `${x} × ${y} mm per 100`;
  };

  const fillPrinterOptions = (target, chosen) => {
    target.replaceChildren();
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "None — print at 100%";
    target.append(none);
    for (const p of printers) {
      const option = document.createElement("option");
      option.value = p.name;
      option.textContent = `${p.name} — prints ${printsAt(p)}`;
      target.append(option);
    }
    target.value = find(chosen) ? chosen : "";
  };

  const applyChoice = () => {
    const chosen = find(select.value);
    scaleX.value = chosen ? String(chosen.factorX) : "";
    scaleY.value = chosen ? String(chosen.factorY) : "";
    removeButton.hidden = !chosen;
    write(CHOSEN, select.value);
  };

  fillPrinterOptions(select, read(CHOSEN) || "");
  applyChoice();
  // This runs at the target before htmx sees the event bubble to the form,
  // so the preview request already carries the new factors.
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

  // null when empty, NaN when not a length, else millimetres.
  const parseMeasured = (field) => {
    const raw = field.value.trim().replace(",", ".");
    if (!raw) return null;
    const value = Number(raw);
    return Number.isFinite(value) && value > 0 ? toMm(value, fields.unit.value) : NaN;
  };

  const outOfRange = (factor) => {
    const equivalent = 100 / factor;
    return equivalent < MIN_MEASURED || equivalent > MAX_MEASURED;
  };

  // The new factors stack on the ones the measured page was printed with,
  // so a second round refines the first instead of throwing it away. An
  // empty left ruler takes the bottom one's measurement.
  const proposed = () => {
    const x = parseMeasured(fields.measured_x);
    const y = parseMeasured(fields.measured_y) ?? x;
    if (x === null || Number.isNaN(x) || Number.isNaN(y)) return { x, y, factors: null };
    const base = find(fields.base.value);
    const round = (f) => Math.round(f * 1e6) / 1e6;
    return {
      x,
      y,
      factors: {
        factorX: round((base ? base.factorX : 1) * (100 / x)),
        factorY: round((base ? base.factorY : 1) * (100 / y)),
      },
    };
  };

  const describe = () => {
    const cm = fields.unit.value === "cm";
    fields.measured_x.placeholder = cm ? "9.85" : "98.5";
    problem.textContent = "";
    result.textContent = "";
    const { x, y, factors } = proposed();
    if (factors === null) return;
    if (outOfRange(factors.factorX) || outOfRange(factors.factorY)) {
      problem.textContent =
        `A ruler that measures ${(outOfRange(factors.factorX) ? x : y).toFixed(1)} mm is ` +
        "off by more than a printer scales. Check that the page printed at 100% / " +
        '"Actual size" on the right paper.';
      return;
    }
    const drawn =
      factors.factorX === factors.factorY
        ? `×${factors.factorX.toFixed(3)}`
        : `×${factors.factorX.toFixed(3)} across and ×${factors.factorY.toFixed(3)} down`;
    const came = x === y ? `${x.toFixed(1)} mm` : `${x.toFixed(1)} × ${y.toFixed(1)} mm`;
    result.textContent =
      `The page will be drawn at ${drawn}, so what came out as ${came} prints as 100 mm.`;
  };

  for (const name of ["measured_x", "measured_y", "unit", "base"]) {
    fields[name].addEventListener("input", describe);
    fields[name].addEventListener("change", describe);
  }

  document.getElementById("calibrate-open").addEventListener("click", () => {
    const chosen = find(select.value);
    fields.name.value = chosen ? chosen.name : "";
    fillPrinterOptions(fields.base, select.value);
    fields.measured_x.value = "";
    fields.measured_y.value = "";
    fields.unit.value = form.elements.unit.value;
    describe();
    dialog.showModal();
    fields.name.focus();
  });

  document.getElementById("calibrate-cancel").addEventListener("click", () => dialog.close());

  calForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const name = fields.name.value.trim();
    const { x, y, factors } = proposed();
    if (!name) {
      problem.textContent = "Give the printer a name.";
      fields.name.focus();
      return;
    }
    if (factors === null) {
      const bottom = x === null || Number.isNaN(x);
      problem.textContent =
        x === null
          ? "Type what the bottom ruler measured."
          : `That is not a length for the ${bottom ? "bottom" : "left"} ruler.`;
      (bottom ? fields.measured_x : fields.measured_y).focus();
      return;
    }
    if (outOfRange(factors.factorX) || outOfRange(factors.factorY)) {
      describe();
      return;
    }
    const entry = {
      name,
      ...factors,
      measuredX: x,
      measuredY: y,
      savedAt: new Date().toISOString(),
    };
    const index = printers.findIndex((p) => p.name === name);
    if (index === -1) printers.push(entry);
    else printers[index] = entry;
    savePrinters();
    fillPrinterOptions(select, name);
    dialog.close();
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
})();
