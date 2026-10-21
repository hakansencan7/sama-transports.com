/* SAMA city labels. City coordinates and names: Natural Earth, public domain. */
(function () {
  'use strict';
  const scriptURL = document.currentScript && document.currentScript.src;
  const dataURL = new URL('cities.json.gz?v=20261021-2', scriptURL || location.href).href;
  const controllers = new WeakMap();
  let dataPromise;
  const languages = new Set(['en', 'tr', 'ar']);
  const normalizeLanguage = value => languages.has(value) ? value : 'en';
  const escapeHTML = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));

  function loadCities() {
    if (!dataPromise) dataPromise = fetch(dataURL).then(async response => {
      if (!response.ok) throw new Error('City labels: HTTP ' + response.status);
      const bytes = new Uint8Array(await response.arrayBuffer());
      const data = bytes[0] === 31 && bytes[1] === 139
        ? await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).json()
        : JSON.parse(new TextDecoder().decode(bytes));
      return data.cities;
    }).catch(error => { dataPromise = null; throw error; });
    return dataPromise;
  }

  function intersects(a, b) {
    return a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
  }

  async function attach(map, options = {}) {
    if (controllers.has(map)) return controllers.get(map);
    let language = normalizeLanguage(options.language || window.SamaLanguage?.lang || document.documentElement.lang);
    let visible = options.visible !== false;
    let destroyed = false;
    let frame = 0;
    let obstacles = [];
    let cities = [];
    const paneName = 'samaCityLabels';
    const pane = map.getPane(paneName) || map.createPane(paneName);
    pane.style.zIndex = '450';
    pane.style.pointerEvents = 'none';
    pane.classList.add('sama-city-pane');
    pane.setAttribute('aria-hidden', 'true');
    const layer = L.layerGroup().addTo(map);
    const context = document.createElement('canvas').getContext('2d');
    const attribution = '<a href="https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-populated-places/" target="_blank" rel="noopener">Natural Earth cities</a>';
    map.attributionControl?.addAttribution(attribution);

    function draw() {
      frame = 0;
      if (destroyed) return;
      layer.clearLayers();
      if (!visible || !cities.length || !map.getZoom()) return;
      const zoom = map.getZoom();
      const bounds = map.getBounds();
      const size = map.getSize();
      const languageIndex = language === 'tr' ? 4 : language === 'ar' ? 5 : 3;
      const occupied = obstacles.slice();
      // Reserve native map controls; their fixed positions should not hide names.
      const mapBox = map.getContainer().getBoundingClientRect();
      map.getContainer().querySelectorAll('.leaflet-control').forEach(control => {
        const box = control.getBoundingClientRect();
        if (box.width && box.height) occupied.push([box.left - mapBox.left - 4, box.top - mapBox.top - 4, box.right - mapBox.left + 4, box.bottom - mapBox.top + 4]);
      });
      const maximum = Math.max(18, Math.min(150, Math.floor(size.x * size.y / 5600)));
      let count = 0;
      for (const city of cities) {
        if (city[6] > zoom + 0.01 || !bounds.contains([city[1], city[2]])) continue;
        const point = map.latLngToContainerPoint([city[1], city[2]]);
        if (point.x < 4 || point.y < 4 || point.x > size.x - 4 || point.y > size.y - 4) continue;
        const name = city[languageIndex] || city[3];
        const major = city[7] || city[8] >= 1000000;
        const fontSize = major ? 13 : 12;
        context.font = `${major ? 700 : 600} ${fontSize}px system-ui, -apple-system, "Segoe UI", sans-serif`;
        const width = Math.ceil(context.measureText(name).width) + 4;
        const height = 19;
        const candidates = [];
        // Wider alternatives keep names readable beside transport circles.
        for (const gap of [9, 20, 31]) candidates.push(
          [point.x + gap, point.y - height / 2],
          [point.x - width - gap, point.y - height / 2],
          [point.x - width / 2, point.y - height - gap],
          [point.x - width / 2, point.y + gap]
        );
        let placement;
        for (const position of candidates) {
          const box = [position[0] - 4, position[1] - 3, position[0] + width + 4, position[1] + height + 3];
          if (box[0] < 4 || box[1] < 4 || box[2] > size.x - 4 || box[3] > size.y - 4 || occupied.some(other => intersects(box, other))) continue;
          placement = position;
          occupied.push(box);
          // A following name must also leave room around this city's anchor dot.
          occupied.push([point.x - 4, point.y - 4, point.x + 4, point.y + 4]);
          break;
        }
        if (!placement) continue;
        const dx = Math.round(placement[0] - point.x);
        const dy = Math.round(placement[1] - point.y);
        const html = `<i class="sama-city-dot${city[7] ? ' is-capital' : ''}"></i><span class="sama-city-name${major ? ' is-major' : ''}" lang="${language}" dir="${language === 'ar' ? 'rtl' : 'ltr'}" style="left:${dx}px;top:${dy}px;width:${width}px">${escapeHTML(name)}</span>`;
        L.marker([city[1], city[2]], {
          pane: paneName, interactive: false, keyboard: false,
          icon: L.divIcon({className:'sama-city-anchor',html,iconSize:[0,0],iconAnchor:[0,0]}),
          zIndexOffset: 0, bubblingMouseEvents: false
        }).addTo(layer);
        if (++count >= maximum) break;
      }
    }

    function refresh() {
      if (destroyed) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(draw);
    }

    const controller = {
      setLanguage(value) { language = normalizeLanguage(value); refresh(); },
      setVisible(value) { visible = Boolean(value); refresh(); },
      setAvoidRects(rects) { obstacles = Array.isArray(rects) ? rects.filter(rect => Array.isArray(rect) && rect.length === 4 && rect.every(Number.isFinite)) : []; refresh(); },
      refresh,
      destroy() {
        if (destroyed) return;
        destroyed = true;
        cancelAnimationFrame(frame);
        map.off('moveend zoomend resize', refresh);
        map.off('unload', controller.destroy);
        document.removeEventListener('sama:languagechange', onLanguageChange);
        layer.clearLayers();
        if (map.hasLayer(layer)) map.removeLayer(layer);
        map.attributionControl?.removeAttribution(attribution);
        controllers.delete(map);
      }
    };
    function onLanguageChange(event) { controller.setLanguage(event.detail?.lang || window.SamaLanguage?.lang || 'en'); }
    controllers.set(map, controller);
    map.on('moveend zoomend resize', refresh);
    map.on('unload', controller.destroy);
    document.addEventListener('sama:languagechange', onLanguageChange);
    try {
      cities = await loadCities();
      if (!destroyed) draw();
    } catch (error) {
      controller.destroy();
      throw error;
    }
    return controller;
  }

  window.SamaCityLabels = {attach};
})();
