(() => {
  const projects = document.querySelector('.projects');
  if (!projects) return;
  projects.classList.add('multimodal-project-gallery');
  const categories = [['All','ALL'],['Mardin','MARDIN'],['Tasucu','TAŞUCU'],['Bamako Arrival','BAMAKO ARRIVAL'],['Gantry','GANTRY UNLOADING'],['Final Positioning','FINAL POSITIONING']];
  projects.innerHTML = `
    <section class="mm-gallery-section" data-multimodal-gallery aria-labelledby="mm-gallery-title">
      <div class="mm-gallery-wrap">
        <div class="mm-gallery-head"><h2 id="mm-gallery-title" class="mm-gallery-title">MULTIMODAL TRANSPORTATION GALLERY</h2></div>
        <div class="mm-filters" role="group" aria-label="Filter photographs by project stage">${categories.map(([value,label],i) => `<button type="button" class="mm-filter${i ? '' : ' active'}" data-category="${value}" aria-pressed="${!i}">${label}</button>`).join('')}</div>
        <p class="mm-status" role="status">Loading project photographs…</p>
        <div class="mm-grid"></div>
      </div>
    </section>
    <div class="mm-lightbox" aria-hidden="true" role="dialog" aria-modal="true" aria-label="Multimodal project photographs">
      <div class="mm-lightbox-head"><span class="mm-lightbox-count" aria-live="polite"></span><button type="button" class="mm-close" aria-label="Close gallery">×</button></div>
      <div class="mm-lightbox-stage"><img alt=""></div>
      <div class="mm-lightbox-footer">
        <button type="button" class="mm-prev" aria-label="Previous image">← PREVIOUS</button>
        <div class="mm-lightbox-info"><div class="mm-lightbox-caption" aria-live="polite"></div><a class="mm-original" target="_blank" rel="noopener">Open original photo ↗</a></div>
        <button type="button" class="mm-next" aria-label="Next image">NEXT →</button>
      </div>
    </div>`;
  const root = projects.querySelector('[data-multimodal-gallery]');
  const grid = root.querySelector('.mm-grid');
  const status = root.querySelector('.mm-status');
  const filters = [...root.querySelectorAll('.mm-filter')];
  const lb = projects.querySelector('.mm-lightbox');
  const lbImg = lb.querySelector('img');
  const lbCaption = lb.querySelector('.mm-lightbox-caption');
  const lbCount = lb.querySelector('.mm-lightbox-count');
  const original = lb.querySelector('.mm-original');
  const prev = lb.querySelector('.mm-prev');
  const next = lb.querySelector('.mm-next');
  const close = lb.querySelector('.mm-close');
  let data = [], filtered = [], current = 0, lastTrigger = null, previousOverflow = '';

  fetch('../assets/gallery/multimodal/gallery.json?v=20260929-originals')
    .then(r => { if (!r.ok) throw new Error('Gallery unavailable'); return r.json(); })
    .then(json => {
      data = json.images;
      applyFilter(root.querySelector('.mm-filter.active').dataset.category);
      status.hidden = true;
    })
    .catch(() => { status.textContent = 'The gallery could not be loaded. Please refresh the page to try again.'; });

  function card(item, index) {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'mm-card';
    el.setAttribute('aria-label', `Open photo ${item.id}: ${item.caption}, ${item.location}`);
    el.innerHTML = `
      <span class="mm-photo"><img src="../${item.thumb}" width="${item.width}" height="${item.height}" alt="${escapeHtml(item.alt)}" loading="${index < 6 ? 'eager' : 'lazy'}" decoding="async"></span>
      <span class="mm-card-caption"><span class="mm-card-copy"><span class="mm-card-title">${escapeHtml(item.caption)}</span><span class="mm-card-location">${escapeHtml(item.location)}</span></span><span class="mm-card-number">${String(item.id).padStart(3, '0')} ↗</span></span>`;
    if (item.thumbWidth < item.width) {
      const img = el.querySelector('img');
      img.srcset = `../${item.thumb} ${item.thumbWidth}w, ../${item.image} ${item.width}w`;
      img.sizes = '(max-width: 600px) 90vw, (max-width: 1000px) 44vw, 29vw';
    }
    el.addEventListener('click', () => openLightbox(index, el));
    return el;
  }
  function applyFilter(category) {
    filtered = category === 'All' ? data : data.filter(x => x.category === category);
    grid.replaceChildren(...filtered.map(card));
  }
  filters.forEach(btn => btn.addEventListener('click', () => {
    filters.forEach(b => { b.classList.toggle('active', b === btn); b.setAttribute('aria-pressed', String(b === btn)); });
    applyFilter(btn.dataset.category);
  }));
  function openLightbox(i, trigger) {
    current = i;
    lastTrigger = trigger;
    previousOverflow = document.body.style.overflow;
    updateLightbox();
    lb.classList.add('open');
    lb.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    close.focus();
  }
  function updateLightbox() {
    const item = filtered[current];
    lbImg.src = '../' + item.image;
    lbImg.alt = item.alt;
    lbImg.width = item.width;
    lbImg.height = item.height;
    lbCaption.textContent = item.caption + ' — ' + item.location;
    lbCount.textContent = `${current + 1} / ${filtered.length}`;
    original.href = '../' + item.image;
  }
  function change(step) {
    current = (current + step + filtered.length) % filtered.length;
    updateLightbox();
  }
  prev.addEventListener('click', () => change(-1));
  next.addEventListener('click', () => change(1));
  close.addEventListener('click', shut);
  lb.addEventListener('click', e => { if (e.target === lb || e.target.classList.contains('mm-lightbox-stage')) shut(); });
  document.addEventListener('keydown', e => {
    if (!lb.classList.contains('open')) return;
    if (e.key === 'Escape') shut();
    if (e.key === 'ArrowLeft') { e.preventDefault(); change(-1); }
    if (e.key === 'ArrowRight') { e.preventDefault(); change(1); }
    if (e.key === 'Tab') {
      const focusable = [close, prev, original, next];
      const index = focusable.indexOf(document.activeElement);
      if (e.shiftKey && index <= 0) { e.preventDefault(); next.focus(); }
      else if (!e.shiftKey && (index === focusable.length - 1 || index === -1)) { e.preventDefault(); close.focus(); }
    }
  });
  let sx = null;
  const stage = lb.querySelector('.mm-lightbox-stage');
  stage.addEventListener('touchstart', e => { sx = e.touches[0].clientX; }, {passive:true});
  stage.addEventListener('touchend', e => {
    if (sx === null) return;
    const dx = e.changedTouches[0].clientX - sx;
    if (Math.abs(dx) > 45) change(dx > 0 ? -1 : 1);
    sx = null;
  }, {passive:true});
  function shut() {
    lb.classList.remove('open');
    lb.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = previousOverflow;
    lbImg.removeAttribute('src');
    if (lastTrigger) lastTrigger.focus();
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  }
})();
