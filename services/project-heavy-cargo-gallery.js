(() => {
  const sources = ["../assets/services/project-heavy-cargo/gallery/01.png","../assets/services/project-heavy-cargo/gallery/02.png","../assets/services/project-heavy-cargo/gallery/03.png","../assets/services/project-heavy-cargo/gallery/04.png","../assets/services/project-heavy-cargo/gallery/05.png","../assets/services/project-heavy-cargo/gallery/06.png","../assets/services/project-heavy-cargo/gallery/07.png","../assets/services/project-heavy-cargo/gallery/08.png","../assets/services/project-heavy-cargo/gallery/09.png","../assets/services/project-heavy-cargo/gallery/10.png","../assets/services/project-heavy-cargo/gallery/11.png","../assets/services/project-heavy-cargo/gallery/12.png","../assets/services/project-heavy-cargo/gallery/13.png","../assets/services/project-heavy-cargo/gallery/14.png","../assets/services/project-heavy-cargo/gallery/15.png","../assets/services/project-heavy-cargo/gallery/16.png","../assets/services/project-heavy-cargo/gallery/17.png","../assets/services/project-heavy-cargo/gallery/18.png","../assets/services/project-heavy-cargo/gallery/19.png","../assets/services/project-heavy-cargo/gallery/20.png","../assets/services/project-heavy-cargo/gallery/21.png","../assets/services/project-heavy-cargo/gallery/22.png","../assets/services/project-heavy-cargo/gallery/23.png","../assets/services/project-heavy-cargo/gallery/24.png","../assets/services/project-heavy-cargo/gallery/25.png","../assets/services/project-heavy-cargo/gallery/26.png","../assets/services/project-heavy-cargo/gallery/27.png"];
  const gallery = document.querySelector(".projects .gallery");
  const hero = document.querySelector(".hero");
  if (!gallery || !hero) return;

  const heroImage = hero.querySelector("img");
  hero.classList.add("project-heavy-cargo-hero");
  heroImage.src = "../assets/services/project-heavy-cargo/hero-project-cargo.png";
  heroImage.alt = "Heavy project cargo prepared for port transport";

  gallery.classList.add("project-heavy-cargo-gallery");
  gallery.innerHTML = sources.map((src, index) =>
    '<button type="button" data-project-photo="' + index + '" aria-label="Open project cargo gallery image ' + (index + 1) + '">' +
      '<img src="' + src + '" alt="Project and heavy cargo transportation operation ' + (index + 1) + '" loading="lazy">' +
    '</button>'
  ).join("");

  const lightbox = document.querySelector(".lightbox");
  const photo = lightbox.querySelector("img");
  const replaceControl = (selector) => {
    const current = lightbox.querySelector(selector);
    const replacement = current.cloneNode(true);
    current.replaceWith(replacement);
    return replacement;
  };
  const closeButton = replaceControl(".close");
  const previousButton = replaceControl(".previous");
  const nextButton = replaceControl(".next");
  let active = 0;

  const show = (index) => {
    active = (index + sources.length) % sources.length;
    photo.src = sources[active];
    photo.alt = "Project and heavy cargo transportation operation " + (active + 1);
  };
  const open = (index) => {
    show(index);
    lightbox.classList.add("open");
  };
  const close = () => lightbox.classList.remove("open");

  gallery.querySelectorAll("[data-project-photo]").forEach((button) => {
    button.addEventListener("click", () => open(Number(button.dataset.projectPhoto)));
  });
  closeButton.addEventListener("click", close);
  previousButton.addEventListener("click", () => show(active - 1));
  nextButton.addEventListener("click", () => show(active + 1));
  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox) close();
  });
  document.addEventListener("keydown", (event) => {
    if (!lightbox.classList.contains("open")) return;
    if (event.key === "ArrowLeft") show(active - 1);
    if (event.key === "ArrowRight") show(active + 1);
  });
})();