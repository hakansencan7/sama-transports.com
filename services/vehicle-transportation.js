(() => {
  const items = [...document.querySelectorAll(".vt-gallery-item")];
  const lightbox = document.querySelector(".vt-lightbox");
  const image = document.querySelector(".vt-lightbox-image");
  const counter = document.querySelector(".vt-counter");
  const closeButton = document.querySelector(".vt-close");
  const previousButton = document.querySelector(".vt-prev");
  const nextButton = document.querySelector(".vt-next");
  if (!items.length || !lightbox || !image || !counter || !closeButton || !previousButton || !nextButton) return;

  let active = 0;
  let touchStartX = null;
  let lastTrigger = null;

  const show = index => {
    active = (index + items.length) % items.length;
    const thumbnail = items[active].querySelector("img");
    image.src = thumbnail.currentSrc || thumbnail.src;
    image.alt = thumbnail.alt;
    counter.textContent = `${String(active + 1).padStart(2, "0")} / ${String(items.length).padStart(2, "0")}`;
  };
  const open = (index, trigger) => {
    lastTrigger = trigger;
    show(index);
    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("vt-lightbox-open");
    closeButton.focus();
  };
  const dismiss = () => {
    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("vt-lightbox-open");
    lastTrigger?.focus();
  };

  items.forEach((item, index) => item.addEventListener("click", () => open(index, item)));
  closeButton.addEventListener("click", dismiss);
  previousButton.addEventListener("click", () => show(active - 1));
  nextButton.addEventListener("click", () => show(active + 1));
  lightbox.addEventListener("click", event => { if (event.target === lightbox) dismiss(); });
  document.addEventListener("keydown", event => {
    if (!lightbox.classList.contains("is-open")) return;
    if (event.key === "Escape") dismiss();
    if (event.key === "ArrowLeft") show(active - 1);
    if (event.key === "ArrowRight") show(active + 1);
  });
  lightbox.addEventListener("touchstart", event => {
    touchStartX = event.changedTouches[0]?.clientX ?? null;
  }, { passive: true });
  lightbox.addEventListener("touchend", event => {
    if (touchStartX === null) return;
    const endX = event.changedTouches[0]?.clientX ?? touchStartX;
    const delta = endX - touchStartX;
    touchStartX = null;
    if (Math.abs(delta) < 48) return;
    show(delta > 0 ? active - 1 : active + 1);
  }, { passive: true });
})();
