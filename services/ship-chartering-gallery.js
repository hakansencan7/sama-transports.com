(() => {
  const gallery = document.querySelector('.ship-chartering-gallery');
  const dialog = document.querySelector('.ship-gallery-lightbox');
  if (!gallery || !dialog || typeof dialog.showModal !== 'function') return;
  const links = [...gallery.querySelectorAll('a')];
  const image = dialog.querySelector('.ship-gallery-full');
  const count = dialog.querySelector('.ship-gallery-count');
  let active = 0;

  const show = index => {
    active = (index + links.length) % links.length;
    image.src = links[active].href;
    image.alt = links[active].querySelector('img').alt;
    count.textContent = `${active + 1} / ${links.length}`;
  };

  gallery.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!links.includes(link) || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    show(links.indexOf(link));
    dialog.showModal();
    document.body.classList.add('ship-gallery-open');
  });
  dialog.querySelector('.ship-gallery-close').addEventListener('click', () => dialog.close());
  dialog.querySelectorAll('[data-direction]').forEach(button => {
    button.addEventListener('click', () => show(active + Number(button.dataset.direction)));
  });
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      show(active + (event.key === 'ArrowLeft' ? -1 : 1));
    }
  });
  dialog.addEventListener('close', () => document.body.classList.remove('ship-gallery-open'));
})();
