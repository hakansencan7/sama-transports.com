(() => {
  if (document.body.dataset.service !== "general-cargo") return;
  const gallery = document.querySelector(".gallery");
  if (!gallery) return;
  const photos = [
    "Steel wire coils and packaged cargo stowed in a vessel hold",
    "Palletized packaged beverages loaded inside a shipping container",
    "Industrial pipes secured with timber supports on a flatbed truck",
    "Forklift handling long industrial pipes at a cargo terminal",
    "Forklift handling wooden crates and cable reels in a vessel hold",
    "Bulk cargo transfer between a vessel and silo trailers at port",
    "Crawler crane being lifted into a cargo vessel hold",
    "Heavy steel components secured on a blue flatbed trailer",
    "Crane loading lattice boom sections onto a flatbed truck",
    "Truck transporting lattice boom sections at a port terminal",
    "Wrapped cargo bales secured on an open-sided truck",
    "Wrapped rolls stowed inside a shipping container",
    "Night-time forklift loading of packaged goods into a trailer",
    "Forklift handling palletized industrial parts beside a truck",
    "Forklift loading stacked metal frames into a curtain-sided trailer"
  ];
  photos.forEach((alt, index) => {
    const name = "general-cargo-gallery-" + String(index + 1).padStart(2, "0");
    const src = "../assets/gallery/general-cargo/" + name + ".webp";
    if ([...gallery.querySelectorAll("[data-full]")].some(item => item.dataset.full === src)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.photo = name;
    button.dataset.full = src;
    button.setAttribute("aria-label", "Open image: " + alt);
    const image = document.createElement("img");
    image.src = "../assets/gallery/general-cargo/" + name + "-preview.webp";
    image.alt = alt;
    image.loading = "lazy";
    image.decoding = "async";
    image.width = 1536;
    image.height = 1024;
    button.append(image);
    gallery.append(button);
  });
})();
