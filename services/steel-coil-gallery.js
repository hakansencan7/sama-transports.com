(() => {
  if (document.body.dataset.service !== "steel-coil") return;
  const gallery = document.querySelector(".gallery");
  if (!gallery) return;
  const photos = [
  "Steel coil loading onto a flatbed truck under a gantry crane",
  "Steel coils secured inside a shipping container",
  "Steel coils stowed in a cargo vessel hold",
  "Steel coil crane handling beside a ship",
  "Steel coil loading onto a truck with a reach stacker",
  "Steel coil port loading and unloading",
  "Upright steel coils secured on rail wagons",
  "Truck fleet at a steel coil logistics yard",
  "Gantry crane loading steel coils onto a flatbed trailer",
  "Crane lifting a steel coil onto a road trailer",
  "Steel coils transported on rail flatbeds",
  "Steel coil cradle and cargo restraint equipment"
];
  photos.forEach((alt, index) => {
    const name = "steel-coil-transportation-" + String(index + 1).padStart(2, "0");
    const src = "../assets/gallery/steel-coil/" + name + ".webp";
    if ([...gallery.querySelectorAll("[data-full]")].some(item => item.dataset.full === src)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.photo = name;
    button.dataset.full = src;
    button.setAttribute("aria-label", "Open image: " + alt);
    const image = document.createElement("img");
    image.src = src;
    image.alt = alt + " — SAMA Transportations";
    image.loading = "lazy";
    image.decoding = "async";
    image.width = 1536;
    image.height = 1024;
    button.append(image);
    gallery.append(button);
  });
})();

