(() => {
  "use strict";
  const form = document.querySelector("#request-form");
  if (!form) return;
  const button = form.querySelector("button[type=submit]");
  const documentInput = form.elements.document;
  const error = document.querySelector("#request-error");
  const status = document.querySelector("#request-status");
  const availability = document.querySelector("#request-availability");
  const retry = document.querySelector("#request-reconnect");
  const service = new URLSearchParams(location.search).get("service");
  if ([...form.elements.service.options].some(option => option.value === service)) {
    form.elements.service.value = service;
  }
  let token = "";
  let tokenTime = 0;
  let attempted = false;
  let busy = false;
  let finished = false;
  let api;
  try {
    api = new URL(form.dataset.apiBase);
    if (api.protocol !== "https:" || api.username || api.password || api.search || api.hash || api.pathname !== "/") {
      throw new Error("Invalid form service configuration");
    }
  } catch {
    availability.textContent = "Online requests are unavailable. Please email operations@sama-transports.com.";
    return;
  }

  function showError(message) {
    error.textContent = message;
    error.hidden = false;
    error.focus();
  }

  async function request(path, options = {}, timeout = 90000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(new URL(path, api), {
        ...options, credentials: "omit", cache: "no-store", redirect: "error",
        signal: controller.signal
      });
      const data = await response.json();
      return { response, data };
    } finally {
      clearTimeout(timer);
    }
  }

  async function connect() {
    button.disabled = true;
    retry.hidden = true;
    availability.hidden = false;
    availability.textContent = "Connecting to our request service…";
    try {
      const { response, data } = await request("/v1/contact/token", {}, 15000);
      if (!response.ok || data.ok !== true || typeof data.token !== "string") {
        throw new Error("Unavailable");
      }
      token = data.token;
      tokenTime = Date.now();
      availability.hidden = true;
      documentInput.disabled = false;
      button.disabled = false;
      button.textContent = "SEND REQUEST";
      return true;
    } catch {
      availability.textContent = "Online requests are temporarily unavailable. You can email operations@sama-transports.com or try connecting again.";
      retry.hidden = false;
      button.textContent = "SERVICE UNAVAILABLE";
      return false;
    }
  }
  retry.addEventListener("click", () => { if (!attempted && !busy && !finished) connect(); });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || finished || !token || !form.reportValidity()) return;
    error.hidden = true;
    const file = documentInput.files[0];
    if (file && (!/\.(pdf|jpe?g|png|txt)$/i.test(file.name) || file.size === 0 || file.size > 5 * 1024 * 1024)) {
      showError("Upload one non-empty PDF, JPG, PNG or TXT document, up to 5 MB.");
      return;
    }
    if (form.elements.loading_date.value && form.elements.delivery_date.value &&
        form.elements.delivery_date.value < form.elements.loading_date.value) {
      showError("Delivery date cannot be earlier than loading date.");
      return;
    }
    busy = true;
    // Renew only before the first attempt. Network retries reuse the original token.
    if (!attempted && Date.now() - tokenTime > 50 * 60 * 1000 && !await connect()) {
      busy = false;
      return;
    }
    const body = new FormData(form);
    if (!file) body.delete("document");
    button.disabled = true;
    button.textContent = "SENDING…";
    form.setAttribute("aria-busy", "true");
    status.textContent = "Sending your request. Please keep this page open.";
    attempted = true;
    try {
      const { response, data } = await request("/v1/contact", {
        method: "POST", headers: { "X-Form-Token": token }, body
      });
      if (!response.ok || data.ok !== true || typeof data.reference !== "string") {
        if (data.code === "status_unknown" || data.code === "changed" || response.status === 403) {
          finished = true;
        }
        showError((data.message || "The request could not be confirmed. Please contact operations.") +
          (data.reference ? " Reference: " + data.reference : ""));
        status.textContent = "Your information remains on this page.";
        return;
      }
      finished = true;
      form.reset();
      status.textContent = "Your request has been accepted for email delivery to our operations team. Reference: " + data.reference;
      status.focus();
    } catch {
      // SMTP may have accepted the message despite a lost HTTP response.
      showError("We could not confirm the delivery status. Retry with the same information to check this request, or contact operations@sama-transports.com. Your information has been kept.");
      status.textContent = "Delivery status unconfirmed.";
    } finally {
      busy = false;
      form.removeAttribute("aria-busy");
      button.disabled = finished;
      button.textContent = finished ? "REQUEST CLOSED" : "SEND REQUEST";
    }
  });
  connect();
})();
