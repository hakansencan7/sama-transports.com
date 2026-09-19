(() => {
  if (document.body.dataset.service !== "transit-transportation") return;
  const stages = [
  [
    "01-transit-road-ankara-derince",
    "ROAD TRANSPORTATION",
    "FROM WAREHOUSE IN ANKARA TO DERINCE PORT",
    "The project cargo was transported by road from the warehouse in Ankara to Derince Port using specialized heavy transport equipment."
  ],
  [
    "02-transit-sea-derince-mariupol",
    "SEA TRANSPORTATION",
    "FROM DERINCE PORT TO MARIUPOL PORT",
    "Following the road transportation stage, the cargo was loaded at Derince Port and transported by sea to Mariupol Port."
  ],
  [
    "03-transit-rail-mariupol-bukhara",
    "RAIL TRANSPORTATION",
    "FROM MARIUPOL PORT TO BUKHARA / UZBEKISTAN",
    "After arrival at Mariupol Port, the cargo continued its journey by rail to Bukhara, Uzbekistan as part of the multimodal transit transportation operation."
  ],
  [
    "04-transit-road-bukhara-dushanbe",
    "ROAD TRANSPORTATION",
    "FROM BUKHARA / UZBEKISTAN TO DUSHANBE / TAJIKISTAN",
    "From Bukhara, Uzbekistan, the cargo was transferred to specialized road transport equipment and transported to Dushanbe, Tajikistan."
  ],
  [
    "05-transit-foundation-dushanbe",
    "FOUNDATION",
    "IN DUSHANBE / TAJIKISTAN",
    "At the final destination in Dushanbe, Tajikistan, the heavy cargo was positioned and installed onto its prepared foundation using specialized engineering and lifting equipment."
  ]
];
  const gallery = document.querySelector(".gallery");
  if (!gallery) return;
  const overview = document.createElement("section");
  overview.className = "transit-operation-overview";
  const heading = document.createElement("h2");
  heading.textContent = "END-TO-END MULTIMODAL TRANSIT OPERATION";
  overview.append(heading);
  const intro = document.createElement("p");
  intro.textContent = "Ankara → Derince Port → Mariupol Port → Bukhara, Uzbekistan → Dushanbe, Tajikistan → Foundation and final positioning. This project brings road, sea and rail transportation together with heavy cargo coordination, multimodal logistics and final positioning.";
  overview.append(intro);
  const list = document.createElement("ol");
  for (const [file, title, route, description] of stages) {
    const item = document.createElement("li");
    const label = document.createElement("h3");
    label.textContent = title + " — " + route;
    const text = document.createElement("p");
    text.textContent = description;
    item.append(label, text);
    list.append(item);
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.photo = file;
    button.dataset.full = "../assets/gallery/transit-transportation/" + file + ".webp";
    button.setAttribute("aria-label", "Open image: " + title + " — " + route);
    const image = document.createElement("img");
    image.src = button.dataset.full;
    image.alt = title + " — " + route + " — illustrative project reconstruction";
    image.width = 1536;
    image.height = 1024;
    image.loading = "lazy";
    image.decoding = "async";
    button.append(image);
    gallery.append(button);
  }
  overview.append(list);
  const note = document.createElement("p");
  note.className = "transit-visual-note";
  note.textContent = "Project visuals are illustrative reconstructions of the transport stages.";
  overview.append(note);
  document.querySelector("#projects").before(overview);
})();

