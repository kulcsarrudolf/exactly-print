// The image field as a drop zone: click it, drop a file on it, or paste one.
//
// The real file input stays inside the label, so clicking and the keyboard
// work as they always did. A dropped or pasted file is put into that input
// and a change event is sent, so htmx, shrink.js and size.js see it exactly
// as if it had been chosen.
(() => {
  const form = document.getElementById("setup");
  const zone = document.querySelector(".dropzone");
  if (!form || !zone) return;
  const input = form.elements.image;
  const thumb = zone.querySelector(".dropzone-thumb");
  const name = zone.querySelector(".dropzone-name");
  const meta = zone.querySelector(".dropzone-meta");
  const remove = document.querySelector(".dropzone-remove");
  const preview = document.getElementById("preview");
  const placeholder = preview && preview.innerHTML;

  let thumbUrl = null;

  const size = (bytes) =>
    bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

  const show = () => {
    const file = input.files && input.files[0];
    if (thumbUrl) URL.revokeObjectURL(thumbUrl);
    thumbUrl = null;
    zone.classList.toggle("has-file", Boolean(file));
    remove.hidden = !file;
    if (!file) {
      thumb.removeAttribute("src");
      return;
    }
    thumbUrl = URL.createObjectURL(file);
    thumb.src = thumbUrl;
    name.textContent = file.name;
    meta.textContent = `${size(file.size)} · click or drop to replace`;
  };

  const use = (files) => {
    const file = [...files].find((f) => f.type.startsWith("image/"));
    if (!file) return false;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };

  // Registered before shrink.js, which may stop the event for a big file.
  form.addEventListener("change", (event) => event.target === input && show(), true);

  // A change that does not bubble still reaches size.js on the input, but not
  // htmx on the form, so no preview is asked for without an image.
  remove.addEventListener("click", () => {
    input.value = "";
    input.dispatchEvent(new Event("change"));
    if (preview) preview.innerHTML = placeholder;
    input.focus();
  });

  // dragenter/dragleave fire for every child; count them to know when the
  // pointer has really left.
  let depth = 0;
  zone.addEventListener("dragenter", (event) => {
    event.preventDefault();
    depth += 1;
    zone.classList.add("dragging");
  });
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
  zone.addEventListener("dragleave", () => {
    depth = Math.max(0, depth - 1);
    if (!depth) zone.classList.remove("dragging");
  });
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    depth = 0;
    zone.classList.remove("dragging");
    use(event.dataTransfer.files);
  });

  // A file dropped beside the zone would otherwise open in the tab.
  window.addEventListener("dragover", (event) => event.preventDefault());
  window.addEventListener("drop", (event) => event.preventDefault());

  // Pasting an image anywhere outside a text field uses it.
  document.addEventListener("paste", (event) => {
    if (event.target.closest("input[type=text], textarea, dialog")) return;
    if (event.clipboardData && use(event.clipboardData.files)) event.preventDefault();
  });

  show();
})();
