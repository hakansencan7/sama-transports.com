(() => {
  const app = document.querySelector("#service-app");
  if (!app) return;

  const heroTitle = app.querySelector(".hero h1");
  if (heroTitle) heroTitle.textContent = "PIPE TRANSPORTATION & LOGISTICS";

  const intro = app.querySelector(".intro");
  if (intro) {
    intro.innerHTML = `
      <div class="intro-grid">
        <div>
          <div class="section-kicker">PIPE LOGISTICS FROM ORIGIN TO FINAL DESTINATION</div>
          <h2>END-TO-END PIPE TRANSPORTATION &amp; LOGISTICS</h2>
          <p class="pipe-intro-slogan">FROM FACTORY FLOOR TO PORT, VESSEL AND FINAL PROJECT SITE.</p>
        </div>
        <div class="pipe-intro-copy">
          <p>Pipe transportation requires much more than moving cargo from one point to another.</p>
          <p>The length, diameter, weight, coating, lifting points and final destination of each pipe shipment must be considered when planning loading, transportation, port operations, vessel handling, securing and final delivery.</p>
          <p>SAMA Transportations provides integrated pipe logistics solutions covering the complete transportation chain from the manufacturing facility to ports, vessels, warehouses, project sites and final customer destinations.</p>
          <p>Our operations can include factory loading, domestic and international road transportation, port receiving, temporary storage, vessel loading, stowage coordination, cargo securing and lashing, sea transportation coordination, vessel discharge, port handling, warehouse transportation, project-site delivery and final unloading.</p>
          <p>Each stage is coordinated according to the technical characteristics of the cargo and the operational requirements of the project.</p>
          <p>Whether the shipment consists of steel pipes, coated line pipes, casing, tubing, structural pipes or other long-length cargo, our objective is to maintain a safe and continuous logistics flow from origin to final delivery.</p>
        </div>
      </div>`;
  }

  const capabilityNames = [
    "FACTORY LOADING",
    "ROAD TRANSPORTATION",
    "INTERNATIONAL TRANSPORT",
    "PORT HANDLING",
    "PORT STORAGE",
    "VESSEL LOADING",
    "STOWAGE COORDINATION",
    "VESSEL LASHING",
    "SEA FREIGHT COORDINATION",
    "VESSEL DISCHARGE",
    "WAREHOUSE TRANSPORT",
    "SITE DELIVERY",
    "FINAL UNLOADING"
  ];
  const capabilities = app.querySelector(".capabilities");
  if (capabilities) {
    capabilities.innerHTML = `
      <div class="section-kicker">PIPE TRANSPORTATION CAPABILITIES</div>
      <h2>OUR PIPE LOGISTICS CAPABILITIES</h2>
      <ul class="cap-list">${capabilityNames.map((item) => `<li>${item}</li>`).join("")}</ul>`;
  }

  const flow = [
    ["01", "FACTORY CARGO PREPARATION", "Before transportation, pipe dimensions, weight, coating condition, lifting requirements and loading configuration are evaluated."],
    ["02", "FACTORY LOADING", "Pipes are loaded onto suitable trailers using cranes or appropriate lifting equipment. Suitable lifting slings, spreader beams or handling equipment should be coordinated according to pipe specifications."],
    ["03", "CARGO SUPPORT & DUNNAGE", "Wooden dunnage, pipe supports, saddles or suitable separation materials are used where required to support the pipes and reduce cargo-to-cargo contact during transportation."],
    ["04", "TRUCK LASHING & SECURING", "After loading, the cargo is secured to the vehicle using an appropriate lashing and securing arrangement. The securing method is selected according to cargo dimensions, weight, trailer configuration and transportation conditions."],
    ["05", "FACTORY-TO-PORT TRANSPORTATION", "Pipes are transported from the manufacturing facility to the nominated port or logistics terminal. For international projects, cross-border road transportation can be coordinated as part of the complete logistics operation."],
    ["06", "PORT RECEIVING & TALLY", "Upon arrival at the port, cargo can be received, counted and checked against transportation and shipment records. Cargo quantity and condition are monitored during the handover process."],
    ["07", "PORT HANDLING", "Cargo is unloaded from trucks and moved to the designated port storage or vessel-loading area using suitable cranes and handling equipment."],
    ["08", "PORT STORAGE / MARSHALLING", "When direct vessel loading is not possible, pipes can be temporarily stored and organized according to shipment sequence, vessel loading plan or project requirements."],
    ["09", "VESSEL LOADING", "Pipes are lifted from the quay or staging area and loaded aboard the vessel using suitable lifting equipment and approved lifting methods."],
    ["10", "STOWAGE", "Cargo is positioned inside the vessel's cargo hold or designated deck area according to the agreed stowage plan. Proper separation, support and cargo distribution should be coordinated to protect the pipes and maintain safe vessel operations."],
    ["11", "VESSEL LASHING & SECURING", "After stowage, pipes are secured aboard the vessel according to the cargo securing requirements. Lashing arrangements may include suitable wires, chains, web lashings, stoppers, chocks or other approved securing systems depending on the cargo and vessel configuration."],
    ["12", "SEA TRANSPORTATION", "After loading and securing, the cargo proceeds to the destination port as part of the international transportation chain."],
    ["13", "VESSEL DISCHARGE", "At the destination port, pipes are safely discharged from the vessel using suitable lifting equipment and coordinated handling procedures."],
    ["14", "PORT-TO-WAREHOUSE TRANSPORT", "Following discharge, cargo can be transferred from the port to designated storage facilities."],
    ["15", "PORT-TO-PROJECT-SITE TRANSPORT", "Where required, pipes can move directly from the port to the project site without intermediate warehousing."],
    ["16", "WAREHOUSE & STORAGE OPERATIONS", "Pipes can be stored, organized and prepared according to customer delivery schedules and project requirements."],
    ["17", "RELOADING", "Cargo is loaded from the storage area onto suitable vehicles for onward transportation. Truck cargo securing and lashing are completed before dispatch."],
    ["18", "INLAND TRANSPORTATION", "Pipes are transported from ports or warehouses to factories, construction sites, oil & gas facilities, infrastructure projects or other customer destinations."],
    ["19", "FINAL-SITE DELIVERY", "The cargo arrives at the final project location according to the planned delivery sequence."],
    ["20", "FINAL UNLOADING", "Final unloading can be coordinated using cranes or other suitable lifting equipment according to the site requirements."]
  ];

  const terms = [
    ["LASHING", "The process of securing cargo to a truck, vessel or transportation platform to restrict unwanted movement during transportation."],
    ["CARGO SECURING", "The complete system used to keep cargo stable during transportation. This can include lashings, chains, webbing, chocks, stoppers, supports and other securing equipment."],
    ["DUNNAGE", "Material placed underneath or between cargo units to support, separate and protect the cargo during handling, transportation and storage."],
    ["CHOCKING", "The use of blocks or mechanical restraints to prevent round cargo such as pipes from rolling or shifting."],
    ["PIPE SADDLES / SUPPORTS", "Special supports used to stabilize pipes and distribute weight while reducing uncontrolled movement."],
    ["STOWAGE", "The planned positioning and arrangement of cargo inside a vessel's hold or on deck."],
    ["STOWAGE PLAN", "The operational plan showing how and where cargo will be positioned aboard the vessel."],
    ["PORT HANDLING", "The physical movement of cargo within the port, including receiving, unloading, staging, storage, lifting and vessel transfer."],
    ["STEVEDORING", "Cargo loading and unloading activities performed at the vessel or port interface."],
    ["VESSEL LOADING", "The operation of transferring cargo from the quay or transport vehicle onto the vessel."],
    ["VESSEL DISCHARGE", "The process of unloading cargo from the vessel at the destination port."],
    ["MARSHALLING / STAGING", "Organizing cargo in a designated area before loading, dispatch or onward transportation."],
    ["TALLY", "The process of counting and recording cargo units during receiving, loading, discharge or delivery operations."],
    ["CARGO SURVEY", "Inspection or verification of cargo condition, quantity and handling status where required."],
    ["LIFTING PLAN", "A planned lifting method defining lifting equipment, lifting points, slings and operational requirements for safe cargo handling."],
    ["SPREADER BEAM", "A lifting beam designed to distribute lifting forces and maintain suitable sling angles when handling long or heavy cargo."],
    ["SLINGS", "Flexible lifting equipment used between the crane hook and cargo during loading or unloading operations."],
    ["BREAKBULK CARGO", "Cargo that is transported as individual pieces rather than inside standard shipping containers. Long steel pipes and project cargo frequently move as breakbulk shipments."],
    ["PROJECT CARGO", "Cargo requiring specialized planning, transportation equipment, lifting methods or operational coordination because of its dimensions, weight or project requirements."],
    ["MULTIMODAL TRANSPORTATION", "The coordinated movement of cargo using more than one mode of transportation, for example: ROAD → PORT → SEA → ROAD → PROJECT SITE."],
    ["FINAL MILE / FINAL DELIVERY", "The last transportation stage from a warehouse, port or distribution location to the customer's final destination or project site."]
  ];

  const pipeTypes = [
    "LINE PIPE",
    "COATED STEEL PIPE",
    "CARBON STEEL PIPE",
    "CASING",
    "TUBING",
    "STRUCTURAL PIPE",
    "LARGE-DIAMETER PIPE",
    "LONG-LENGTH PIPE",
    "PROJECT PIPE CARGO",
    "OIL & GAS PIPE",
    "INDUSTRIAL PIPE",
    "INFRASTRUCTURE PIPE"
  ];

  const industries = [
    "OIL & GAS",
    "ENERGY",
    "PETROCHEMICAL",
    "WATER INFRASTRUCTURE",
    "PIPELINE PROJECTS",
    "CONSTRUCTION",
    "INDUSTRIAL PROJECTS",
    "MARINE & PORT PROJECTS"
  ];

  const safetyItems = [
    "LIFTING CONTROL",
    "PIPE SUPPORT & DUNNAGE",
    "TRUCK CARGO SECURING",
    "VESSEL LASHING",
    "CONTROLLED HANDLING",
    "FINAL-SITE SAFETY"
  ];

  const projects = app.querySelector(".projects");
  if (projects) {
    const deepContent = document.createElement("div");
    deepContent.className = "pipe-detail-content";
    deepContent.innerHTML = `
      <section class="pipe-deep-section pipe-flow-section" aria-labelledby="pipe-flow-title">
        <div class="pipe-section-heading">
          <div>
            <div class="section-kicker">OPERATIONS / 20 STAGES</div>
            <h2 id="pipe-flow-title">COMPLETE PIPE LOGISTICS FLOW</h2>
          </div>
          <p>A coordinated process that connects technical cargo preparation, road movement, port handling, vessel operations and final-site delivery.</p>
        </div>
        <ol class="pipe-flow">${flow.map(([index, title, description]) => `<li class="pipe-flow-item"><span class="pipe-flow-index">${index}</span><h3>${title}</h3><p>${description}</p></li>`).join("")}</ol>
      </section>

      <section class="pipe-deep-section pipe-terms-section" aria-labelledby="pipe-terms-title">
        <div class="pipe-section-heading">
          <div>
            <div class="section-kicker">OPERATIONAL REFERENCE</div>
            <h2 id="pipe-terms-title">PIPE LOGISTICS TERMINOLOGY</h2>
          </div>
          <p>Clear terminology supports more precise planning, handovers and cargo-control decisions throughout a pipe logistics operation.</p>
        </div>
        <div class="pipe-terms">${terms.map(([title, description]) => `<article class="pipe-term"><h3>${title}</h3><p>${description}</p></article>`).join("")}</div>
      </section>

      <section class="pipe-deep-section pipe-cargo-section" aria-labelledby="pipe-types-title">
        <div class="pipe-cargo-layout">
          <div>
            <div class="section-kicker">CARGO PROFILE</div>
            <h2 id="pipe-types-title">PIPE CARGO WE HANDLE</h2>
          </div>
          <p>Planning is matched to the pipe's dimensions, coating, loading arrangement and the operational demands of its final destination.</p>
        </div>
        <div class="pipe-cargo-grid">${pipeTypes.map((item) => `<span>${item}</span>`).join("")}</div>
      </section>

      <section class="pipe-deep-section pipe-industry-section" aria-labelledby="pipe-industries-title">
        <div class="pipe-cargo-layout">
          <div>
            <div class="section-kicker">PROJECT ENVIRONMENTS</div>
            <h2 id="pipe-industries-title">INDUSTRIES WE SUPPORT</h2>
          </div>
          <p>From pipeline construction and energy developments to marine and industrial projects, every move is planned around the operational sequence.</p>
        </div>
        <div class="pipe-industry-grid">${industries.map((item) => `<span>${item}</span>`).join("")}</div>
      </section>

      <section class="pipe-deep-section pipe-safety-section" aria-labelledby="pipe-safety-title">
        <div class="pipe-safety-copy">
          <div class="section-kicker">CONTROLLED OPERATIONS</div>
          <h2 id="pipe-safety-title">SAFE HANDLING AT EVERY STAGE</h2>
          <p>Pipe cargo presents specific handling and transportation challenges because of its length, weight and cylindrical shape.</p>
          <p>Our logistics planning focuses on suitable lifting arrangements, cargo support, controlled handling and appropriate securing throughout every stage of the transportation chain.</p>
          <p>From crane lifting and port operations to truck lashing and vessel securing, each operation is coordinated according to cargo characteristics and project requirements.</p>
        </div>
        <div class="pipe-safety-grid">${safetyItems.map((item, index) => `<article class="pipe-safety-card"><span>${String(index + 1).padStart(2, "0")}</span><h3>${item}</h3></article>`).join("")}</div>
      </section>

      <section class="pipe-deep-section pipe-final-message" aria-labelledby="pipe-final-title">
        <div class="pipe-final-message-inner">
          <div class="section-kicker">SAMA PIPE LOGISTICS</div>
          <h2 id="pipe-final-title">ONE CARGO.<br>ONE LOGISTICS PLAN.<br><strong>FROM FACTORY TO FINAL SITE.</strong></h2>
          <p>From factory loading and port operations to vessel transport, discharge, warehousing and final project delivery, SAMA Transportations coordinates every stage of your pipe logistics operation.</p>
        </div>
      </section>

      <section class="pipe-deep-section pipe-cta-section" aria-labelledby="pipe-cta-title">
        <div>
          <div class="section-kicker">PROJECT ENQUIRIES</div>
          <h2 id="pipe-cta-title">PLANNING A PIPE TRANSPORTATION PROJECT?</h2>
        </div>
        <div>
          <p>Send us your pipe specifications, quantity, dimensions, weight, origin, port of loading and final destination. Our team will evaluate the handling and transportation requirements and develop the right logistics solution for your project.</p>
          <div class="pipe-actions">
            <a class="pipe-button pipe-button-primary" href="../index.html#contact">REQUEST A PIPE LOGISTICS QUOTE</a>
            <a class="pipe-button pipe-button-secondary" href="../index.html#contact">DISCUSS YOUR PROJECT</a>
          </div>
        </div>
      </section>`;
    projects.before(deepContent);
  }

  if (!projects) return;

  const projectsKicker = projects.querySelector(".section-kicker");
  const projectsTitle = projects.querySelector("h2");
  const projectsNote = projects.querySelector(".projects-note");
  const projectNumber = projects.querySelector(".project-number");
  const projectTitle = projects.querySelector(".project h3");
  const projectMeta = projects.querySelector(".project-meta");
  if (projectsKicker) projectsKicker.textContent = "PIPE OPERATIONS / GALLERY";
  if (projectsTitle) projectsTitle.textContent = "PIPE TRANSPORTATION GALLERY";
  if (projectsNote) projectsNote.textContent = "Approved Pipe Transportation poster references. Select any image to view the full, uncropped artwork.";
  if (projectNumber) projectNumber.textContent = "PIPE LOGISTICS / OPERATION REFERENCES";
  if (projectTitle) projectTitle.textContent = "PIPE TRANSPORTATION GALLERY";
  if (projectMeta) {
    projectMeta.innerHTML = `
      <div><b>OPERATIONS</b>Factory, road, port, vessel and final-site pipe logistics.</div>
      <div><b>FORMAT</b>Approved poster artwork shown without additional overlays or cropping.</div>
      <div><b>VIEWING</b>Select an image for full-size navigation across the complete gallery.</div>`;
  }

  const gallery = projects.querySelector(".gallery");
  const sourceImages = Array.from({ length: 33 }, (_, index) => `../assets/services/pipe-transportation/gallery/${String(index + 1).padStart(2, "0")}.png`);
  if (!gallery) return;

  gallery.classList.add("pipe-gallery");
  const legacyCards = Array.from(gallery.querySelectorAll("button"));
  const photos = legacyCards.map((card, index) => {
    const image = card.querySelector("img");
    image.loading = "lazy";
    image.decoding = "async";
    image.alt = `Existing Pipe Transportation gallery image ${index + 1}`;
    card.removeAttribute("data-photo");
    card.dataset.pipePhoto = String(index);
    card.setAttribute("aria-label", `Open Pipe Transportation gallery image ${index + 1}`);
    return { src: image.getAttribute("src") || image.src, alt: image.alt, card };
  });

  sourceImages.forEach((src, sourceIndex) => {
    const index = photos.length;
    const card = document.createElement("button");
    const image = document.createElement("img");
    card.type = "button";
    card.dataset.pipePhoto = String(index);
    card.setAttribute("aria-label", `Open Pipe Transportation poster ${sourceIndex + 1}`);
    image.src = src;
    image.alt = `Pipe Transportation operation poster ${sourceIndex + 1}`;
    image.loading = "lazy";
    image.decoding = "async";
    card.append(image);
    gallery.append(card);
    photos.push({ src, alt: image.alt, card });
  });

  const oldLightbox = document.querySelector(".lightbox");
  if (!oldLightbox) return;
  const lightbox = oldLightbox.cloneNode(true);
  oldLightbox.replaceWith(lightbox);
  const lightboxImage = lightbox.querySelector("img");
  const controls = lightbox.querySelector(".lightbox-controls");
  const closeButton = lightbox.querySelector(".close");
  controls.innerHTML = `
    <button class="previous" type="button" aria-label="View previous gallery image">← PREVIOUS</button>
    <span class="pipe-lightbox-count" aria-live="polite"></span>
    <button class="next" type="button" aria-label="View next gallery image">NEXT →</button>`;
  const previousButton = controls.querySelector(".previous");
  const nextButton = controls.querySelector(".next");
  const count = controls.querySelector(".pipe-lightbox-count");
  let activeIndex = 0;
  let lastTrigger = null;
  let touchStartX = null;

  const show = (index) => {
    activeIndex = (index + photos.length) % photos.length;
    const photo = photos[activeIndex];
    lightboxImage.src = photo.src;
    lightboxImage.alt = photo.alt;
    lightboxImage.decoding = "async";
    count.textContent = `${String(activeIndex + 1).padStart(2, "0")} / ${String(photos.length).padStart(2, "0")}`;
  };

  const open = (index, trigger) => {
    lastTrigger = trigger || null;
    show(index);
    lightbox.classList.add("open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("pipe-gallery-modal-open");
    closeButton.focus();
  };

  const close = () => {
    lightbox.classList.remove("open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("pipe-gallery-modal-open");
    if (lastTrigger) lastTrigger.focus();
  };

  photos.forEach((photo, index) => {
    photo.card.onclick = () => open(index, photo.card);
  });

  closeButton.onclick = close;
  previousButton.onclick = () => show(activeIndex - 1);
  nextButton.onclick = () => show(activeIndex + 1);
  lightbox.onclick = (event) => {
    if (event.target === lightbox) close();
  };

  document.addEventListener("keydown", (event) => {
    if (!lightbox.classList.contains("open")) return;
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
    if (delta > 0) show(activeIndex - 1);
    else show(activeIndex + 1);
  }, { passive: true });

  lightbox.setAttribute("aria-hidden", "true");
})();
