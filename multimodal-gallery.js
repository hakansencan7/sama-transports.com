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
      <div class="mm-lightbox-stage"><div class="mm-lightbox-poster"></div></div>
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
  const lbPoster = lb.querySelector('.mm-lightbox-poster');
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

  const featureIcons = [
    '<path d="M5 17V8h14v9M3 19h18M9 8V5h6v3M9 12v3m6-3v3"/>',
    '<path d="M3 7h11v10H3zM14 10h4l3 4v3h-7M6 7V4h6M6 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm12 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/>',
    '<path d="m12 3 2.5 2 3.2-.2.8 3.1L21 10l-1.5 2.8.2 3.2-3.1.8L14 20l-2.8-1.5-3.2.2-.8-3.1L4 13l1.5-2.8-.2-3.2 3.1-.8L12 3Z"/><path d="m9 11 2 2 4-4"/>',
    '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6z"/><path d="m8 12 3 3 5-6"/>'
  ];
  const features = [
    ['HEAVY CARGO','EXPERTISE'],['INTEGRATED','TRANSPORT'],['EXPERIENCED','TEAM'],['ON-TIME','DELIVERY']
  ];
  function poster(item, index = 0, full = false) {
    const src = '../' + (full ? item.image : item.thumb);
    const responsive = !full && item.thumbWidth < item.width
      ? ` srcset="../${item.thumb} ${item.thumbWidth}w, ../${item.image} ${item.width}w" sizes="(max-width: 540px) 90vw, (max-width: 860px) 44vw, 29vw"` : '';
    const loading = full || index < 6 ? 'eager' : 'lazy';
    return `<span class="mm-poster">
      <span class="mm-poster-head">
        <span class="mm-poster-heading"><span class="mm-poster-title">MULTIMODAL<strong>TRANSPORTATION</strong></span><span class="mm-poster-subtitle">ROAD · SEA · RAIL · PROJECT LOGISTICS</span></span>
        <span class="mm-poster-trust">TRUSTED LOGISTICS<br>WORLDWIDE</span>
      </span>
      <span class="mm-poster-photo">
        <img class="mm-photo-backdrop" src="${src}" alt="" aria-hidden="true" loading="${loading}" decoding="async">
        <img class="mm-poster-image" src="${src}" width="${item.width}" height="${item.height}" alt="${escapeHtml(item.alt)}" loading="${loading}" decoding="async"${responsive}>
      </span>
      <span class="mm-poster-foot">
        <span class="mm-poster-caption"><b>${escapeHtml(item.caption)}</b><span>${escapeHtml(item.location)} · ${String(item.id).padStart(3,'0')}</span></span>
        <span class="mm-poster-features">${features.map((label, i) => `<span class="mm-poster-feature"><span class="mm-feature-icon"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round">${featureIcons[i]}</svg></span><span>${label[0]}<br>${label[1]}</span></span>`).join('')}</span>
        <span class="mm-poster-baseline"><span>◎</span> CONNECTING INDUSTRIES ACROSS BORDERS<span class="mm-poster-rule"></span></span>
      </span>
    </span>`;
  }
  function card(item, index) {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'mm-card';
    el.setAttribute('aria-label', `Open photo ${item.id}: ${item.caption}, ${item.location}`);
    el.innerHTML = poster(item, index);
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
    lbPoster.innerHTML = poster(item, current, true);
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
    lbPoster.replaceChildren();
    if (lastTrigger) lastTrigger.focus();
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  }
})();
