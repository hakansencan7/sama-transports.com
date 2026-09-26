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
  for (const [, title, route, description] of stages) {
    const item = document.createElement("li");
    const label = document.createElement("h3");
    label.textContent = title + " — " + route;
    const text = document.createElement("p");
    text.textContent = description;
    item.append(label, text);
    list.append(item);
  }
  overview.append(list);
  document.querySelector("#projects").before(overview);
  const photos = [
  [
    "transit-project-01.webp",
    "ROAD TRANSPORTATION",
    "FROM WAREHOUSE IN ANKARA TO DERINCE PORT",
    "Ankara depot loading and road transportation"
  ],
  [
    "transit-project-02.webp",
    "SEA TRANSPORTATION",
    "FROM DERINCE PORT TO MARIUPOL PORT",
    "Port trailer, ship hold cargo, cargo with drums, ship at night"
  ],
  [
    "transit-project-03.webp",
    "RAIL TRANSPORTATION",
    "FROM MARIUPOL PORT TO BUKHARA / UZBEKISTAN",
    "Industrial transformer on rail wagons, close rail load, blue crane unloading, empty road trailer by the crane"
  ],
  [
    "transit-project-04.webp",
    "RAIL TRANSPORTATION",
    "FROM MARIUPOL PORT TO BUKHARA / UZBEKISTAN",
    "Cargo on road trailer under crane, cargo on red supports, close transformer side, load on trailer beside rail locomotive"
  ],
  [
    "transit-project-05.webp",
    "RAIL TRANSPORTATION",
    "FROM MARIUPOL PORT TO BUKHARA / UZBEKISTAN",
    "Cargo raised on red steel supports, yellow hydraulic jack closeup, support and jack closeup, load on trailer at dusk"
  ],
  [
    "transit-project-06.webp",
    "ROAD TRANSPORTATION",
    "FROM BUKHARA / UZBEKISTAN TO DUSHANBE / TAJIKISTAN",
    "Orange heavy truck and transformer load in yard from four different angles"
  ],
  [
    "transit-project-07.webp",
    "ROAD TRANSPORTATION",
    "FROM BUKHARA / UZBEKISTAN TO DUSHANBE / TAJIKISTAN",
    "Transformer convoy passing industrial gate, convoy on city street, orange truck driving hillside road, front view of orange truck"
  ],
  [
    "transit-project-08.webp",
    "ROAD TRANSPORTATION",
    "FROM BUKHARA / UZBEKISTAN TO DUSHANBE / TAJIKISTAN",
    "Transformer on long multi-axle trailer: side view, rough roadside, rear view on mountain road, distant convoy in mountain valley"
  ],
  [
    "transit-project-09.webp",
    "ROAD TRANSPORTATION",
    "FROM BUKHARA / UZBEKISTAN TO DUSHANBE / TAJIKISTAN",
    "Convoy rear with crew on mountain road, overhead clearance bar near village, unpaved approach road, site arrival with crew"
  ],
  [
    "transit-project-10.webp",
    "FOUNDATION",
    "IN DUSHANBE / TAJIKISTAN",
    "Crew with yellow lifting supports, hydraulic control station under load, rear wide site view, side view of transformer with yellow gantry equipment"
  ],
  [
    "transit-project-11.webp",
    "FOUNDATION",
    "IN DUSHANBE / TAJIKISTAN",
    "Transformer on supports with rails and crane, rear with hydraulic equipment and crew, hydraulic control console closeup, front view of supported transformer"
  ],
  [
    "transit-project-12.webp",
    "FOUNDATION",
    "IN DUSHANBE / TAJIKISTAN",
    "Four distinct views of transformer, red multi-axle trailer, yellow lifting gantry and site crew beside electrical substation"
  ],
  [
    "transit-project-13.webp",
    "FOUNDATION",
    "IN DUSHANBE / TAJIKISTAN",
    "Rear view with workers, side view with orange crane, close crew underneath load beside yellow supports, front view and substation"
  ],
  [
    "transit-project-14.webp",
    "FOUNDATION",
    "IN DUSHANBE / TAJIKISTAN",
    "Yellow skid base closeup, workers under side of transformer, load with yellow supports and crew, kneeling worker operating positioning equipment"
  ]
];
  for (const [file, title, route, caption] of photos) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.photo = file;
    button.dataset.full = "../assets/gallery/transit-transportation/" + file;
    button.setAttribute("aria-label", "Open image: " + title + " — " + route + ": " + caption);
    const image = document.createElement("img");
    image.src = button.dataset.full;
    image.alt = title + " — " + route + ": " + caption;
    image.width = 2172;
    image.height = 724;
    image.loading = "eager";
    image.decoding = "async";
    button.append(image);
    gallery.append(button);
  }
})();
