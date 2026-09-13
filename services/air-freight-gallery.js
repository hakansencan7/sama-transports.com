(() => {
  'use strict';

  const gallery = document.getElementById('af-gallery');
  const lightbox = document.getElementById('af-gallery-lightbox');

  if (!gallery || !lightbox) return;

  const items = Array.from(gallery.querySelectorAll('.af-gallery-item'));
  const image = lightbox.querySelector('img');
  const previous = lightbox.querySelector('.af-lightbox-previous');
  const next = lightbox.querySelector('.af-lightbox-next');
  const close = lightbox.querySelector('.af-lightbox-close');
  const count = lightbox.querySelector('.af-lightbox-count');
  let activeIndex = 0;
  let lastFocusedElement = null;
  let touchStartX = null;

  const setImage = (index) => {
    activeIndex = (index + items.length) % items.length;
    const item = items[activeIndex];
    image.src = item.dataset.full || item.querySelector('img').src;
    image.alt = item.dataset.alt || item.querySelector('img').alt;
    count.textContent = `${activeIndex + 1} / ${items.length}`;
  };

  const open = (index) => {
    lastFocusedElement = document.activeElement;
    setImage(index);
    lightbox.classList.add('is-open');
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.classList.add('af-lightbox-open');
    close.focus();
  };

  const closeLightbox = () => {
    lightbox.classList.remove('is-open');
    lightbox.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('af-lightbox-open');
    if (lastFocusedElement instanceof HTMLElement) lastFocusedElement.focus();
  };

  items.forEach((item, index) => {
    item.addEventListener('click', () => open(index));
  });

  previous.addEventListener('click', () => setImage(activeIndex - 1));
  next.addEventListener('click', () => setImage(activeIndex + 1));
  close.addEventListener('click', closeLightbox);

  lightbox.addEventListener('click', (event) => {
    if (event.target === lightbox) closeLightbox();
  });

  document.addEventListener('keydown', (event) => {
    if (!lightbox.classList.contains('is-open')) return;
    if (event.key === 'Escape') closeLightbox();
    if (event.key === 'ArrowLeft') setImage(activeIndex - 1);
    if (event.key === 'ArrowRight') setImage(activeIndex + 1);
  });

  lightbox.addEventListener('touchstart', (event) => {
    touchStartX = event.changedTouches[0].clientX;
  }, { passive: true });

  lightbox.addEventListener('touchend', (event) => {
    if (touchStartX === null) return;
    const deltaX = event.changedTouches[0].clientX - touchStartX;
    touchStartX = null;
    if (Math.abs(deltaX) < 48) return;
    setImage(deltaX > 0 ? activeIndex - 1 : activeIndex + 1);
  }, { passive: true });
})();
