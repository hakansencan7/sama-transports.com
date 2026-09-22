(() => {
  const form = document.querySelector("#request-form");
  if (!form) return;
  const service = new URLSearchParams(location.search).get("service");
  if ([...form.elements.service.options].some(option => option.value === service)) form.elements.service.value = service;
  // Email delivery is deliberately deferred. Never POST or claim success.
  form.addEventListener("submit", event => {
    event.preventDefault();
    document.querySelector("#request-availability").focus();
  });
})();
