// The other side of the printed size, filled in from the image.
//
// The server already keeps the image's proportions when one side is left
// empty; this shows the number that will come out instead of a blank field.
// The side the user typed is theirs; the other is "auto" and follows it,
// until the user types into it too. Clearing a side hands it back to auto.
(() => {
  const form = document.getElementById("setup");
  if (!form) return;
  const file = form.elements.image;
  const unit = form.elements.unit;
  const sides = { width: form.elements.width, height: form.elements.height };
  const other = { width: "height", height: "width" };

  // Pixels of the chosen image, once it has been read.
  let image = null;
  // Which side follows the other: "width", "height" or null.
  let auto = null;

  const parse = (field) => {
    const raw = field.value.trim().replace(",", ".");
    if (!raw) return null;
    const value = Number(raw);
    return Number.isFinite(value) && value > 0 ? value : NaN;
  };

  // A tenth of a millimetre, the precision the preview reports.
  const format = (value) => {
    const decimals = unit.value === "cm" ? 2 : 1;
    return value.toFixed(decimals).replace(/\.?0+$/, "");
  };

  const mark = (name) => {
    for (const side of Object.keys(sides)) {
      const isAuto = side === name;
      sides[side].classList.toggle("auto", isAuto);
      const badge = sides[side].labels[0].querySelector(".auto-badge");
      if (badge) badge.hidden = !isAuto;
    }
    auto = name;
  };

  // Fill the auto side from the other one; empty when there is nothing to follow.
  const follow = () => {
    if (!auto) return;
    const target = sides[auto];
    const from = parse(sides[other[auto]]);
    if (from === null || Number.isNaN(from) || !image) {
      target.value = "";
      return;
    }
    const ratio = auto === "height" ? image.h / image.w : image.w / image.h;
    target.value = format(from * ratio);
  };

  const typed = (name) => {
    const field = sides[name];
    const partner = other[name];
    if (field.value.trim()) {
      // A typed side is never auto; the other side follows it unless the
      // user has typed that one as well.
      if (auto === name) mark(null);
      if (auto === partner || !sides[partner].value.trim()) mark(partner);
    } else if (sides[partner].value.trim() && auto !== partner) {
      // Cleared next to a typed side: this side follows it again.
      mark(name);
    } else {
      // Cleared and the other side only followed this one: both empty.
      mark(null);
      sides[partner].value = "";
    }
    follow();
  };

  for (const name of Object.keys(sides)) {
    sides[name].addEventListener("input", () => typed(name));
  }
  unit.addEventListener("change", follow);

  file.addEventListener("change", () => {
    image = null;
    const chosen = file.files && file.files[0];
    if (!chosen) {
      follow();
      return;
    }
    const url = URL.createObjectURL(chosen);
    const probe = new Image();
    probe.onload = () => {
      URL.revokeObjectURL(url);
      if (file.files[0] !== chosen) return;
      // naturalWidth/Height honour the EXIF orientation, as the server does.
      image = { w: probe.naturalWidth, h: probe.naturalHeight };
      if (!auto) {
        const w = sides.width.value.trim();
        const h = sides.height.value.trim();
        if (w && !h) mark("height");
        else if (h && !w) mark("width");
      }
      follow();
    };
    probe.onerror = () => {
      URL.revokeObjectURL(url);
      follow();
    };
    probe.src = url;
  });
})();
