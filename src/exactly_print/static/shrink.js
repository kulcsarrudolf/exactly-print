// Big images are made smaller in the browser before they are sent.
//
// The server takes images up to 25 MB, but a hosted function has a lower
// ceiling on each request and each response; on Vercel it is 4.5 MB. An
// image over LIMIT is therefore re-encoded here as a JPEG that fits, before
// htmx asks for the preview or the form asks for the PDF. A print only ever
// needs so many pixels: the count is capped where A3 at 300 dpi stops
// gaining, so nothing a printer could show is lost.
(() => {
  const LIMIT = 3.5 * 1024 * 1024;
  // About what A3 needs at 300 dpi, and within the canvas area iOS allows.
  const MAX_PIXELS = 16_000_000;
  const MIN_SIDE = 1000;
  const QUALITIES = [0.9, 0.8];

  const form = document.getElementById("setup");
  const preview = document.getElementById("preview");
  if (!form || !preview) return;
  const input = form.elements.image;

  // The file being shrunk, and the submit button pressed meanwhile.
  let working = null;
  let queued = null;

  const say = (text, kind) => {
    const p = document.createElement("p");
    p.className = kind;
    p.textContent = text;
    preview.replaceChildren(p);
  };
  const mb = (bytes) => (bytes / 1024 / 1024).toFixed(1);

  const decode = (file) =>
    new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("not an image"));
      };
      img.src = url;
    });

  const encode = (canvas, quality) =>
    new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));

  // A JPEG of the image under LIMIT, with fewer pixels only when it has to.
  const shrink = async (file) => {
    const img = await decode(file);
    // naturalWidth/Height and drawImage both honour the EXIF orientation,
    // as the server does.
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    if (!w || !h) throw new Error("not an image");
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    let scale = Math.min(1, Math.sqrt(MAX_PIXELS / (w * h)));
    while (Math.max(w, h) * scale >= MIN_SIDE) {
      canvas.width = Math.round(w * scale);
      canvas.height = Math.round(h * scale);
      // Transparent areas turn white, as they do on the server.
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      for (const quality of QUALITIES) {
        const blob = await encode(canvas, quality);
        if (blob && blob.size <= LIMIT) return blob;
      }
      scale *= 0.8;
    }
    throw new Error("still too large");
  };

  const replace = (blob, original) => {
    const stem = original.name.replace(/\.[^.]+$/, "") || "image";
    const file = new File([blob], `${stem}.jpg`, { type: "image/jpeg" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
  };

  const run = async (file) => {
    working = file;
    say(`Shrinking the ${mb(file.size)} MB image…`, "placeholder");
    let problem = null;
    try {
      replace(await shrink(file), file);
    } catch (e) {
      // Reported below, unless another file has been chosen since.
      problem = e;
    }
    if (working !== file) return;
    working = null;
    const button = queued;
    queued = null;
    if (problem) {
      input.value = "";
      say(
        problem.message === "not an image"
          ? "That file is not an image the browser can read."
          : `The ${mb(file.size)} MB image could not be made small enough to send. ` +
              "Choose a smaller one.",
        "error",
      );
      return;
    }
    // The small file is now what htmx and the PDF form see.
    input.dispatchEvent(new Event("change", { bubbles: true }));
    if (button) button.click();
  };

  // htmx listens on the form for both events; catching them on the way
  // down keeps the big file from being sent while its replacement is made.
  const guard = (event) => {
    if (event.target !== input) return;
    const file = input.files && input.files[0];
    if (!file) {
      working = null;
      return;
    }
    if (file.size <= LIMIT) {
      working = null;
      return;
    }
    event.stopImmediatePropagation();
    if (working !== file) run(file);
  };
  form.addEventListener("input", guard, true);
  form.addEventListener("change", guard, true);

  form.addEventListener("submit", (event) => {
    if (!working) return;
    event.preventDefault();
    queued = event.submitter;
  });
})();
