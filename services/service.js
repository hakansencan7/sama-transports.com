const SERVICES = {
  "turkey-warehousing": {
    image: "turkey-warehousing-cargo-handling-hero.webp",
    n: "02",
    title: "TURKEY WAREHOUSING & CARGO HANDLING",
    intro: "SAMA Transportations coordinates receiving, storage, handling and onward dispatch in Turkey for cargo that needs a controlled handover. Our team plans each movement around cargo condition, access requirements and delivery timing, keeping the next transport stage clear, traceable and ready to proceed.",
    caps: ["Warehouse coordination", "Loading and unloading", "Cargo handling", "Secure staging", "Inventory-ready storage", "Onward transport support"]
  },
  "syria-warehousing": {
    n: "03",
    title: "SYRIA WAREHOUSING & CARGO HANDLING",
    intro: "Our Syria warehousing and cargo handling service supports a controlled flow from operational receiving through storage and dispatch preparation. Each handover is planned around cargo care, safe stacking and transport readiness, helping shipments move to the next stage with documented coordination and practical local support.",
    caps: ["Warehouse coordination", "Loading and unloading", "Cargo handling", "Secure stacking", "Cargo staging", "Heavy handling support"]
  },
  "jordan-warehousing": {
    n: "04",
    title: "JORDAN WAREHOUSING & CARGO HANDLING",
    intro: "SAMA Transportations provides Jordan warehousing and cargo-handling support for shipments requiring careful receiving, storage and onward planning. We coordinate each step around cargo condition, secure staging and release timing, so handovers between warehouse, transport and delivery teams remain organised and ready for the next movement.",
    caps: ["Warehouse coordination", "Cargo receiving", "Loading and unloading", "Secure storage", "Cargo staging", "Distribution support"]
  },
  "pipe-transportation": {
    n: "07",
    title: "PIPE TRANSPORTATION",
    image: "hero-pipe-transportation.png",
    intro: "SAMA Transportations plans pipe movements around length, diameter, weight, coating and lifting requirements from origin through final delivery. Our teams coordinate safe loading, cargo support, road and port handling, securing and handovers so every shipment follows a practical, controlled logistics sequence.",
    caps: ["Pipe loading support", "Cargo securing", "Route planning", "Handling coordination", "Delivery scheduling", "Cross-border logistics"],
    gallery: true
  },
  "rail-freight": {
    n: "08",
    title: "RAIL FREIGHT",
    image: "hero-rail-freight.png",
    gallery: true,
    intro: "Our rail freight service integrates rail into a broader cargo plan with clear terminal, transfer and onward-delivery coordination. We prepare each movement around cargo readiness, schedule requirements and intermodal handovers, helping customers connect rail capacity with practical road, port or final-destination logistics support.",
    caps: ["Rail movement planning", "Terminal coordination", "Intermodal transfers", "Cargo preparation", "Schedule coordination", "Onward delivery support"]
  },
  "transit-transportation": {
    gallery: true,
    n: "09",
    title: "TRANSIT TRANSPORTATION",
    intro: "SAMA Transportations coordinates transit cargo through each gateway with attention to documentation, timing and border readiness. We plan the route, cargo handovers and onward transportation together, giving every shipment a practical operational path from entry point to final destination across regional trade corridors.",
    caps: ["Transit route planning", "Border coordination", "Document readiness", "Cargo monitoring", "Schedule management", "Onward transport support"]
  },
  "ship-chartering": {
    n: "10",
    title: "SHIP CHARTERING SERVICES",
    intro: "Our ship chartering service supports cargo owners with coordinated vessel, port and shipment planning. We review the movement requirements alongside cargo readiness and schedule needs, then connect the necessary operational steps so each chartered shipment can progress with clear handovers and dependable logistics support.",
    caps: ["Chartering coordination", "Vessel requirement review", "Port liaison", "Cargo readiness", "Schedule support", "Shipment planning"]
  },
  "multimodal-transportation": {
    n: "11",
    title: "MULTIMODAL TRANSPORTATION",
    image: "hero-multimodal-transportation.png",
    intro: "SAMA Transportations combines road, sea, rail and terminal activity into one integrated cargo plan. We coordinate transfers, schedules and documentation between each mode, helping complex project movements retain continuity from origin through ports, inland routes and final-site delivery without unnecessary operational gaps.",
    caps: ["Modal planning", "Road and sea coordination", "Rail integration", "Transfer management", "Cargo visibility", "End-to-end planning"],
    gallery: true
  },
  "living-container": {
    n: "12",
    title: "LIVING CONTAINER TRANSPORTATION",
    image: "living-container-hero.webp",
    imageAlt: "Yellow truck loading a white living container outside an industrial facility",
    gallery: true,
    intro: "SAMA Transportations coordinates living-container movements with careful planning for lifting, loading, route access and site readiness. Each unit is handled around its dimensions and delivery conditions, allowing collection, transport and placement to follow a controlled sequence from origin through final positioning.",
    caps: ["Container movement planning", "Secure loading", "Route coordination", "Handling support", "Delivery scheduling", "Site readiness coordination"]
  },
  "steel-coil": {
    gallery: true,
    n: "13",
    title: "STEEL COIL TRANSPORTATION",
    image: "hero-steel-coil.png",
    intro: "Steel coil transportation demands secure handling, matched equipment and controlled cargo restraint. SAMA Transportations plans loading, supports, routing and delivery around each coil’s dimensions and handling requirements, helping maintain stability and clear operational control from collection through final unloading.",
    caps: ["Coil handling support", "Secure loading", "Cargo restraint planning", "Route coordination", "Equipment matching", "Delivery management"]
  },
  "general-cargo": {
    n: "14",
    gallery: true,
    image: "general-cargo-hero.webp",
    imageAlt: "SAMA Transportation General Cargo Handling and Transportation",
    title: "GENERAL CARGO TRANSPORTATION",
    intro: "SAMA Transportation offers flexible transport and handling solutions for packaged goods, machinery and industrial materials. From loading and unloading to port handling and cargo transfers, we coordinate your shipments with care, efficiency and a focus on safe, reliable delivery.",
    caps: ["Road transport planning", "Cargo coordination", "Loading support", "Route management", "Cross-border support", "Delivery coordination"]
  },
  "customs-clearance": {
    n: "15",
    gallery: true,
    title: "CUSTOMS CLEARANCE SERVICES",
    image: "customs-clearance-four-countries-dark.svg",
    imageAlt: "Customs emblems representing Iraq, Turkey, Syria and Jordan",
    tagline: "CUSTOMS CLEARANCE IN IRAQ, TURKEY, SYRIA & JORDAN",
    intro: "SAMA provides customs clearance services in Iraq, Turkey, Syria and Jordan. We coordinate documentation, border procedures and shipment follow-up, helping our customers manage their import, export and transit operations with clear communication and reliable support.",
    caps: ["Document coordination", "Customs process support", "Border liaison", "Cargo readiness", "Transit support", "Status communication"]
  },
  "heavy-equipment-transportation": {
    n: "16",
    title: "HEAVY EQUIPMENT TRANSPORTATION",
    tagline: "SPECIALIZED TRANSPORT SOLUTIONS FOR CONSTRUCTION & INDUSTRIAL EQUIPMENT",
    image: "cover.png",
    intro: "SAMA Transportations moves excavators, wheel loaders, bulldozers, cranes and other industrial machinery with specialised lowbed equipment and route-led planning. We coordinate loading, securing, permits and handovers around the machine’s dimensions and destination, keeping each heavy-equipment movement safe and operationally controlled.",
    caps: ["Construction machinery transport", "Lowbed transportation", "Oversized equipment transport", "Route planning", "Loading and securing", "Port-to-site transportation", "Cross-border transportation"],
    gallery: true
  }
};

const key = document.body.dataset.service;
const service = SERVICES[key];
if (!service) throw new Error("Unknown service");

const REQUEST_SERVICES = {"turkey-warehousing":"Warehousing & Cargo Handling","syria-warehousing":"Warehousing & Cargo Handling","jordan-warehousing":"Warehousing & Cargo Handling","pipe-transportation":"Pipe Transportation","rail-freight":"Rail Freight","transit-transportation":"Transit Transportation","ship-chartering":"Ship Chartering","multimodal-transportation":"Multimodal Transportation","living-container":"Other","steel-coil":"Steel Coil Transportation","general-cargo":"General Cargo Transportation","customs-clearance":"Customs Clearance","heavy-equipment-transportation":"Heavy Equipment Transportation"};
const requestHref = "../contact.html?service=" + encodeURIComponent(REQUEST_SERVICES[key] || "Other");
const image = `../assets/services/${key}/${service.image || "cover.svg"}`;
const nav = `<header class="site-header"><a class="brand" href="../index.html">S<b>A</b>MA<small>TRANSPORTATIONS</small></a><nav class="nav"><a href="../index.html">Home</a><a href="../index.html#about">About Us</a><a class="services-link" href="../index.html#services">Our Services</a><a href="../index.html#regions">Regions</a><a href="../index.html#fleet">Fleet</a><a href="../contact.html">Contact</a></nav><a class="track" href="https://track.sama-transports.com">SAMA TRACK ↗</a></header>`;
const galleryTitle = `${service.title} GALLERY`;
const galleryMarkup = service.gallery
  ? `<div class="gallery" aria-live="polite"></div>`
  : `<p class="gallery-empty">Approved gallery source files are not included in this site package for this service.</p>`;

document.querySelector("#service-app").innerHTML = `${nav}
  <main>
    <section class="hero"><img src="${image}" alt="${service.imageAlt || service.title}" fetchpriority="high"><div class="hero-copy"><div class="eyebrow">${service.n} / SERVICE</div><h1>${service.title.replace(" & ", " &amp;<br>")}</h1>${service.tagline ? `<p class="hero-tagline">${service.tagline}</p>` : ""}</div></section>
    <section class="intro"><div class="intro-grid"><div><div class="section-kicker">SERVICE OVERVIEW</div><h2>PLANNED FOR CONFIDENT CARGO MOVEMENT.</h2></div><p>${service.intro}</p></div></section>
    <section class="projects" id="projects"><div class="projects-head"><h2>${galleryTitle}</h2></div>${galleryMarkup}</section>
    <details class="service-details"><summary>READ MORE</summary><section class="capabilities"><div class="section-kicker">SERVICE CAPABILITIES</div><h2>READY FOR THE NEXT MOVE</h2><ul class="cap-list">${service.caps.map(capability => `<li>${capability}</li>`).join("")}</ul></section></details>
    <section class="service-cta" aria-labelledby="service-cta-title"><div><div class="section-kicker">PROJECT ENQUIRIES</div><h2 id="service-cta-title">PLAN YOUR NEXT MOVE WITH SAMA</h2></div><a class="service-cta-link" href="${requestHref}">REQUEST THIS SERVICE <span aria-hidden="true">↗</span></a></section>
  </main>
  <div class="lightbox" aria-hidden="true" aria-modal="true" role="dialog" aria-label="Service gallery image viewer"><div class="lightbox-box"><button class="close" type="button" aria-label="Close gallery">×</button><img src="" alt=""><div class="lightbox-controls gallery-lightbox-controls"><button class="previous gallery-lightbox-nav gallery-lightbox-nav--previous" type="button">← PREVIOUS</button><span class="gallery-lightbox-count" aria-live="polite"></span><button class="next gallery-lightbox-nav gallery-lightbox-nav--next" type="button">NEXT →</button></div></div></div>`;

const gallery = document.querySelector(".gallery");
const lightbox = document.querySelector(".lightbox");
const lightboxImage = lightbox.querySelector("img");
const count = lightbox.querySelector(".gallery-lightbox-count");
const closeButton = lightbox.querySelector(".close");
const previousButton = lightbox.querySelector(".previous");
const nextButton = lightbox.querySelector(".next");
let active = 0;
let lastTrigger = null;
let touchStartX = null;

const galleryItems = () => [...document.querySelectorAll(".gallery [data-photo]")];
const show = index => {
  const items = galleryItems();
  if (!items.length) return;
  active = (index + items.length) % items.length;
  const item = items[active];
  const imageElement = item.querySelector("img");
  lightboxImage.src = item.dataset.full || imageElement.currentSrc || imageElement.src;
  lightboxImage.alt = item.dataset.alt || imageElement.alt;
  count.textContent = `${String(active + 1).padStart(2, "0")} / ${String(items.length).padStart(2, "0")}`;
};
const open = (index, trigger) => {
  lastTrigger = trigger;
  show(index);
  lightbox.classList.add("open");
  lightbox.setAttribute("aria-hidden", "false");
  document.body.classList.add("gallery-modal-open");
  closeButton.focus();
};
const close = () => {
  lightbox.classList.remove("open");
  lightbox.setAttribute("aria-hidden", "true");
  document.body.classList.remove("gallery-modal-open");
  if (lastTrigger) lastTrigger.focus();
};

gallery?.addEventListener("click", event => {
  const button = event.target.closest("[data-photo]");
  if (!button) return;
  const items = galleryItems();
  open(items.indexOf(button), button);
});
closeButton.addEventListener("click", close);
previousButton.addEventListener("click", () => show(active - 1));
nextButton.addEventListener("click", () => show(active + 1));
lightbox.addEventListener("click", event => { if (event.target === lightbox) close(); });
document.addEventListener("keydown", event => {
  if (!lightbox.classList.contains("open")) return;
  if (event.key === "Escape") close();
  if (event.key === "ArrowLeft") show(active - 1);
  if (event.key === "ArrowRight") show(active + 1);
});
lightbox.addEventListener("touchstart", event => { touchStartX = event.changedTouches[0]?.clientX ?? null; }, { passive: true });
lightbox.addEventListener("touchend", event => {
  if (touchStartX === null) return;
  const endX = event.changedTouches[0]?.clientX ?? touchStartX;
  const delta = endX - touchStartX;
  touchStartX = null;
  if (Math.abs(delta) < 44) return;
  show(delta > 0 ? active - 1 : active + 1);
}, { passive: true });
