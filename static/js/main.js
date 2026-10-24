document.addEventListener("DOMContentLoaded", () => {
  // Disable the submit button after the first click (stops duplicate complaints, NFR-04/05)
  document.querySelectorAll("form[data-once]").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector("button[type=submit]");
      if (btn) {
        btn.disabled = true;
        btn.dataset.label = btn.textContent;
        btn.textContent = "Submitting…";
      }
    });
    // Re-enable if the user comes back with the browser Back button
    window.addEventListener("pageshow", () => {
      const btn = form.querySelector("button[type=submit]");
      if (btn && btn.dataset.label) {
        btn.disabled = false;
        btn.textContent = btn.dataset.label;
      }
    });

    // Live character counter on long text boxes
    form.querySelectorAll("textarea").forEach((ta) => {
      const out = document.createElement("small");
      out.className = "help";
      ta.insertAdjacentElement("afterend", out);
      const update = () => { out.textContent = `${ta.value.length} characters`; };
      ta.addEventListener("input", update);
      update();
    });
  });
});