(() => {
  const projects = document.querySelector('.projects');
  if (!projects) return;

  projects.classList.add('multimodal-project-gallery');
  projects.innerHTML = `
    <section class="mm-gallery-section" data-multimodal-gallery>
      <div class="mm-gallery-wrap">
        <div class="mm-gallery-head">
          <div>
            <div class="mm-gallery-kicker">Project Gallery</div>
            <h2 class="mm-gallery-title">MARDIN → BAMAKO<br>MULTIMODAL PROJECT</h2>
          </div>
          <p class="mm-gallery-sub">Heavy project cargo transported through an integrated road, port, sea and final-site delivery operation from Mardin, Turkey to Bamako, Mali.</p>
        </div>
        <div class="mm-filters">
          <button type="button" class="mm-filter active" data-category="All">ALL</button>
          <button type="button" class="mm-filter" data-category="Mardin">MARDIN</button>
          <button type="button" class="mm-filter" data-category="Tasucu">TAŞUCU</button>
          <button type="button" class="mm-filter" data-category="Bamako Arrival">BAMAKO ARRIVAL</button>
          <button type="button" class="mm-filter" data-category="Gantry">GANTRY UNLOADING</button>
          <button type="button" class="mm-filter" data-category="Final Positioning">FINAL POSITIONING</button>
        </div>
        <div class="mm-grid"></div>
        <div class="mm-more-wrap"><button type="button" class="mm-more">VIEW MORE</button></div>
      </div>
    </section>
    <div class="mm-lightbox" aria-hidden="true" role="dialog" aria-modal="true">
      <button type="button" class="mm-close" aria-label="Close gallery">×</button>
      <button type="button" class="mm-prev" aria-label="Previous image">‹</button>
      <img alt="">
      <button type="button" class="mm-next" aria-label="Next image">›</button>
      <div class="mm-lightbox-caption"></div>
    </div>`;

  const root = document.querySelector('[data-multimodal-gallery]');
  if (!root) return;

  const grid = root.querySelector('.mm-grid');
  const moreBtn = root.querySelector('.mm-more');
  const filters = [...root.querySelectorAll('.mm-filter')];
  const lb = document.querySelector('.mm-lightbox');
  const lbImg = lb.querySelector('img');
  const lbCaption = lb.querySelector('.mm-lightbox-caption');
  const prev = lb.querySelector('.mm-prev');
  const next = lb.querySelector('.mm-next');
  const close = lb.querySelector('.mm-close');

  let data = [];
  let filtered = [];
  let visible = 12;
  let initialLoad = 12;
  let batchSize = 12;
  let current = 0;

  fetch('../assets/gallery/multimodal/gallery.json')
    .then(r => r.json())
    .then(json => {
      data = json.images;
      filtered = data;
      batchSize = json.loadMore || 12;
      initialLoad = json.initialLoad || batchSize;
      visible = initialLoad;
      render();
    });

  function card(item, index) {
    const el = document.createElement('article');
    el.className = 'mm-card';
    el.innerHTML = `
      <img src="../${item.thumb}" data-full="../${item.image}" alt="${escapeHtml(item.alt)}" loading="lazy" decoding="async">
      <div class="mm-meta"><strong>${escapeHtml(item.caption)}</strong><span>${escapeHtml(item.location)}</span></div>`;
    el.addEventListener('click', () => openLightbox(index));
    return el;
  }

  function render() {
    grid.innerHTML = '';
    filtered.slice(0, visible).forEach((item, i) => grid.appendChild(card(item, i)));
    moreBtn.style.display = visible >= filtered.length ? 'none' : 'inline-block';
  }

  moreBtn.addEventListener('click', () => {
    visible += batchSize;
    render();
  });

  filters.forEach(btn => btn.addEventListener('click', () => {
    filters.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const cat = btn.dataset.category;
    filtered = cat === 'All' ? data : data.filter(x => x.category === cat);
    visible = initialLoad;
    render();
  }));

  function openLightbox(i) {
    current = i;
    updateLightbox();
    lb.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function updateLightbox() {
    const item = filtered[current];
    lbImg.src = '../' + item.image;
    lbImg.alt = item.alt;
    lbCaption.textContent = item.caption + ' — ' + item.location;
  }

  function change(step) {
    current = (current + step + filtered.length) % filtered.length;
    updateLightbox();
  }

  prev.addEventListener('click', e => {e.stopPropagation(); change(-1)});
  next.addEventListener('click', e => {e.stopPropagation(); change(1)});
  close.addEventListener('click', shut);
  lb.addEventListener('click', e => {if(e.target === lb) shut()});
  document.addEventListener('keydown', e => {
    if (!lb.classList.contains('open')) return;
    if (e.key === 'Escape') shut();
    if (e.key === 'ArrowLeft') change(-1);
    if (e.key === 'ArrowRight') change(1);
  });

  let sx = null;
  lb.addEventListener('touchstart', e => sx = e.touches[0].clientX, {passive:true});
  lb.addEventListener('touchend', e => {
    if (sx === null) return;
    const dx = e.changedTouches[0].clientX - sx;
    if (Math.abs(dx) > 45) change(dx > 0 ? -1 : 1);
    sx = null;
  }, {passive:true});

  function shut(){
    lb.classList.remove('open');
    document.body.style.overflow = '';
    lbImg.src = '';
  }
  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  }
})();
