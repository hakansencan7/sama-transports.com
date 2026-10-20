/* SAMA shared English / Turkish / Arabic language navigation. */
(() => {
  'use strict';
  if (window.SamaLanguage) return;
  const scriptUrl = document.currentScript.src;
  const dictionaryBase = new URL('.', scriptUrl);
  const rootUrl = new URL('../../', dictionaryBase);
  const supported = ['en', 'tr', 'ar'];
  const normalize = value => String(value ?? '').replace(/\s+/g, ' ').trim();
  const dictionary = Object.create(null);
  const aliases = Object.create(null);
  const textState = new WeakMap();
  const attributeState = new WeakMap();
  const skip = 'script,style,noscript,svg,code,pre,[translate="no"],[data-no-translate],.brand,.sama-languagebar';
  const attributes = ['alt', 'title', 'placeholder', 'aria-label', 'content'];
  let saved;
  try { saved = localStorage.getItem('sama_main_lang'); } catch (_) {}
  const requested = new URLSearchParams(location.search).get('lang');
  const browser = (navigator.language || 'en').slice(0, 2).toLowerCase();
  let language = [requested, saved, browser, 'en'].find(code => supported.includes(code));
  let ready = false;
  let observer;
  let frame = 0;
  const pending = new Set();

  function translate(source, target = language) {
    const key = normalize(source);
    const entry = dictionary[key] || aliases[key];
    if (entry && entry[target] !== undefined) return entry[target];
    // Gallery counters contain changing numbers; keep their numbers unchanged.
    let match = key.match(/^Open image (\d+) of (\d+):\s*(.*)$/i);
    if (match && target !== 'en') {
      const label = target === 'tr' ? `${match[2]} görselden ${match[1]}. görseli aç` : `افتح الصورة ${match[1]} من ${match[2]}`;
      return `${label}: ${translate(match[3], target)}`;
    }
    match = key.match(/^(\d+\s*\/\s*)(SERVICE|IRAQ|PORT|STORAGE|BULK|ROAD|PROJECT|LIQUID|TRANSIT|MARINE|RAIL|CONTAINERS|TRANSPORT|PLANNING|SAFETY|PERFORMANCE)$/);
    if (match) return match[1] + translate(match[2], target);
    match = key.match(/^(.*) GALLERY$/);
    if (match && target !== 'en') {
      const subject = translate(match[1], target);
      return target === 'tr' ? `${subject} GALERİSİ` : `معرض ${subject}`;
    }
    return source;
  }

  function register(entries) {
    for (const [source, value] of Object.entries(entries || {})) {
      const key = normalize(source);
      dictionary[key] = { ...(dictionary[key] || {}), ...value };
    }
    for (const entry of Object.values(dictionary)) {
      for (const value of Object.values(entry)) {
        if (typeof value === 'string' && !aliases[normalize(value)]) aliases[normalize(value)] = entry;
      }
    }
  }

  function processText(node) {
    const parent = node.parentElement;
    if (!parent || parent.closest(skip) || !normalize(node.nodeValue)) return;
    let state = textState.get(node);
    if (!state || node.nodeValue !== state.last) state = { source: node.nodeValue, last: node.nodeValue };
    if (parent.tagName === 'OPTION' && !parent.hasAttribute('value')) parent.setAttribute('value', parent.value);
    const source = state.source;
    const contextualKey = parent.getAttribute('data-i18n-key');
    const translated = translate(contextualKey && dictionary[contextualKey] ? contextualKey : normalize(source));
    const leading = source.match(/^\s*/)[0], trailing = source.match(/\s*$/)[0];
    const next = leading + translated + trailing;
    if (node.nodeValue !== next) node.nodeValue = next;
    state.last = next;
    textState.set(node, state);
  }

  function processAttributes(element) {
    if (element.closest(skip)) return;
    const previous = attributeState.get(element) || {};
    for (const name of attributes) {
      if (!element.hasAttribute(name)) continue;
      const value = element.getAttribute(name);
      let state = previous[name];
      if (!state || value !== state.last) state = { source: value, last: value };
      const next = translate(state.source);
      if (value !== next) element.setAttribute(name, next);
      state.last = next;
      previous[name] = state;
    }
    attributeState.set(element, previous);
  }

  function processSubtree(node) {
    if (!node || !node.isConnected) return;
    if (node.nodeType === Node.TEXT_NODE) { processText(node); return; }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    if (node.closest(skip)) return;
    processAttributes(node);
    const texts = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    let text;
    while ((text = texts.nextNode())) processText(text);
    node.querySelectorAll('[alt],[title],[placeholder],[aria-label],meta[content]').forEach(processAttributes);
  }

  function observe() {
    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: attributes });
  }

  function refresh(nodes = [document.documentElement]) {
    if (!ready) return;
    observer?.disconnect();
    for (const node of nodes) processSubtree(node);
    if (observer) observe();
  }

  function updateButtons() {
    document.querySelectorAll('.sama-language-button').forEach(button => {
      const selected = button.dataset.samaLang === language;
      button.classList.toggle('is-active', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    const label = document.querySelector('.sama-language-label');
    if (label) label.textContent = { en: 'LANGUAGE', tr: 'DİL', ar: 'اللغة' }[language];
  }

  function setLanguage(next, { updateUrl = true } = {}) {
    if (!supported.includes(next)) return;
    language = next;
    document.documentElement.lang = next;
    document.documentElement.dir = next === 'ar' ? 'rtl' : 'ltr';
    document.body.dir = next === 'ar' ? 'rtl' : 'ltr';
    try { localStorage.setItem('sama_main_lang', next); } catch (_) {}
    if (updateUrl) {
      try { const url = new URL(location.href); url.searchParams.set('lang', next); history.replaceState(history.state, '', url); } catch (_) {}
    }
    updateButtons();
    refresh();
    if (ready) document.dispatchEvent(new CustomEvent('sama:languagechange', { detail: { lang: next }, bubbles: true }));
  }

  window.SamaLanguage = {
    get lang() { return language; },
    get ready() { return ready; },
    t: translate,
    set: setLanguage,
    register,
    refresh: () => refresh(),
    has: source => Boolean(dictionary[normalize(source)] || aliases[normalize(source)])
  };

  function installBar() {
    document.documentElement.classList.add('sama-language-enabled');
    const bar = document.createElement('div');
    bar.className = 'sama-languagebar';
    bar.setAttribute('translate', 'no');
    bar.setAttribute('role', 'navigation');
    bar.setAttribute('aria-label', 'Language / Dil / اللغة');
    bar.innerHTML = `<div class="sama-language-inner"><a class="sama-language-home" href="${new URL('index.html', rootUrl).href}" aria-label="SAMA Transportations">SAMA <span>TRANSPORTATIONS</span></a><div class="sama-language-options"><span class="sama-language-label"></span><button type="button" class="sama-language-button" data-sama-lang="en" lang="en" title="English">ENG</button><button type="button" class="sama-language-button" data-sama-lang="tr" lang="tr" title="Türkçe">TUR</button><button type="button" class="sama-language-button" data-sama-lang="ar" lang="ar" title="العربية">العربية</button></div></div>`;
    document.body.prepend(bar);
    bar.addEventListener('click', event => {
      const button = event.target.closest('[data-sama-lang]');
      if (button) setLanguage(button.dataset.samaLang);
    });
  }

  function loadDictionary(filename) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = new URL(filename + '?v=20261020-1', dictionaryBase).href;
      script.onload = resolve;
      script.onerror = () => reject(new Error('Language dictionary could not be loaded: ' + filename));
      document.head.appendChild(script);
    });
  }

  installBar();
  setLanguage(language, { updateUrl: false });
  // Preserve the chosen language even where browser storage is unavailable.
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || link.hasAttribute('download')) return;
    const raw = link.getAttribute('href');
    if (!raw || raw.startsWith('#') || /^(mailto|tel|javascript):/i.test(raw)) return;
    try {
      const url = new URL(link.href, location.href);
      if (url.origin === location.origin && (/\.html$/.test(url.pathname) || url.pathname.endsWith('/'))) {
        url.searchParams.set('lang', language);
        link.href = url.href;
      }
    } catch (_) {}
  }, true);
  window.addEventListener('storage', event => {
    if (event.key === 'sama_main_lang' && supported.includes(event.newValue)) setLanguage(event.newValue);
  });

  observer = new MutationObserver(records => {
    for (const record of records) {
      if (record.type === 'childList') record.addedNodes.forEach(node => pending.add(node));
      else pending.add(record.target);
    }
    if (!frame && pending.size) frame = requestAnimationFrame(() => {
      frame = 0;
      const nodes = [...pending]; pending.clear();
      refresh(nodes);
    });
  });
  const files = ['site-dictionary.js'];
  if (document.body.classList.contains('sama-atlas')) files.push('map-dictionary.js');
  Promise.all(files.map(loadDictionary)).then(() => {
    ready = true;
    setLanguage(language, { updateUrl: false });
    observe();
  }).catch(error => {
    console.error(error);
    ready = true;
    setLanguage(language, { updateUrl: false });
    observe();
  });
})();
