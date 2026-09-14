(() => {
  const gallery = document.querySelector("#pc-project-gallery");
  const lightbox = document.querySelector("#pc-gallery-lightbox");
  if (!gallery || !lightbox) return;

  const photos = Array.from({ length: 28 }, (_, index) => ({
    src: `../assets/services/project-heavy-cargo/gallery/${String(index + 1).padStart(2, "0")}.png`,
    alt: `Project and heavy cargo transportation operation ${index + 1}`
  }));
  const image = lightbox.querySelector("img");
  const closeButton = lightbox.querySelector(".pc-lightbox-close");
  const previousButton = lightbox.querySelector(".pc-lightbox-previous");
  const nextButton = lightbox.querySelector(".pc-lightbox-next");
  const count = lightbox.querySelector(".pc-lightbox-count");
  let activeIndex = 0;
  let trigger = null;
  let touchStartX = null;

  gallery.innerHTML = photos.map((photo, index) => (
    `<button type="button" data-project-photo="${index}" data-image-label="VIEW ${String(index + 1).padStart(2, "0")}" aria-label="Open ${photo.alt}">` +
      `<img src="${photo.src}" alt="${photo.alt}" loading="lazy" decoding="async">` +
    "</button>"
  )).join("");

  const show = (index) => {
    activeIndex = (index + photos.length) % photos.length;
    const photo = photos[activeIndex];
    image.src = photo.src;
    image.alt = photo.alt;
    count.textContent = `${String(activeIndex + 1).padStart(2, "0")} / ${String(photos.length).padStart(2, "0")}`;
  };

  const open = (index, button) => {
    trigger = button;
    show(index);
    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    closeButton.focus();
  };

  const close = () => {
    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    trigger?.focus();
  };

  gallery.querySelectorAll("[data-project-photo]").forEach((button) => {
    button.addEventListener("click", () => open(Number(button.dataset.projectPhoto), button));
  });
  closeButton.addEventListener("click", close);
  previousButton.addEventListener("click", () => show(activeIndex - 1));
  nextButton.addEventListener("click", () => show(activeIndex + 1));
  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox) close();
  });
  document.addEventListener("keydown", (event) => {
    if (!lightbox.classList.contains("is-open")) return;
    if (event.key === "Escape") close();
    if (event.key === "ArrowLeft") show(activeIndex - 1);
    if (event.key === "ArrowRight") show(activeIndex + 1);
  });
  lightbox.addEventListener("touchstart", (event) => {
    touchStartX = event.changedTouches[0]?.clientX ?? null;
  }, { passive: true });
  lightbox.addEventListener("touchend", (event) => {
    if (touchStartX === null) return;
    const endX = event.changedTouches[0]?.clientX ?? touchStartX;
    const delta = endX - touchStartX;
    touchStartX = null;
    if (Math.abs(delta) < 44) return;
    show(delta > 0 ? activeIndex - 1 : activeIndex + 1);
  }, { passive: true });
})();
