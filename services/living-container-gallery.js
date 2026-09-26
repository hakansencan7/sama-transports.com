(() => {
  if (document.body.dataset.service !== "living-container") return;

  const gallery = document.querySelector(".gallery");
  if (!gallery) return;

  const photos = [
    "Row of modular units in an open project yard",
    "Crane lifting a white living container beside a yellow truck",
    "Living container being loaded onto a yellow truck",
    "White truck transporting a living container outside a factory",
    "Long accommodation unit being positioned on a red truck trailer",
    "White truck with a living container and secured equipment",
    "Crane loading a living container onto a white truck",
    "Yellow truck and crane handling a white living container",
    "Red truck carrying a living container in a loading yard",
    "Red truck with a living container on a factory access road",
    "White truck carrying a modular load under a protective cover",
    "Side view of a long living container on a road trailer",
    "Loaded living-container trucks waiting for project dispatch",
    "Rear view of a red trailer carrying a white living container",
    "Escort vehicle and two rows of living-container transport trucks",
    "Two rows of trucks prepared to transport modular living units",
    "Rear view of a living container on a trailer in a dispatch queue",
    "Site worker and a line of trailers carrying living containers"
  ];

  const items = document.createDocumentFragment();
  photos.forEach((alt, index) => {
    const name = "living-container-gallery-" + String(index + 1).padStart(2, "0");
    const src = "../assets/gallery/living-container/" + name + ".webp";
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
    items.append(button);
  });
  gallery.append(items);
})();
