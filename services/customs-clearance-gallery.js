(() => {
  if (document.body.dataset.service !== "customs-clearance") return;
  const gallery = document.querySelector(".gallery");
  if (!gallery) return;
  const photos = [
    ["iraq-safwan", "Customs clearance services in Iraq – Safwan Border Crossing"],
    ["turkey-habur", "Customs clearance services in Turkey – Habur Border Crossing"],
    ["syria-nasib", "Customs clearance services in Syria – Nasib Border Crossing"],
    ["jordan-jaber", "Customs clearance services in Jordan – Jaber Border Crossing"]
  ];
  photos.forEach(([country, alt]) => {
    const name = "customs-clearance-" + country;
    const src = "../assets/gallery/customs-clearance/" + name + ".webp";
    if ([...gallery.querySelectorAll("[data-full]")].some(item => item.dataset.full === src)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.photo = name;
    button.dataset.full = src;
    button.setAttribute("aria-label", "Open image: " + alt);
    const image = document.createElement("img");
    image.src = src;
    image.alt = alt;
    image.loading = "eager";
    image.decoding = "async";
    image.width = 1536;
    image.height = 1024;
    button.append(image);
    gallery.append(button);
  });
})();
