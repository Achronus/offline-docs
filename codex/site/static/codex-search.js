// codex-search.js
//
// Tiny in-iframe search overlay for sources whose native search depends on
// cloud services (Algolia DocSearch — i.e. React, Next.js). Injected into
// each staged page by the ingest stager when the source is marked with
// `custom_search: true` in codex.yaml.
//
// Loads /sources/<name>/_codex_search.json (a small list of {url, title,
// headings, snippet} entries built from the staged HTML), opens a modal on
// Ctrl+K / Cmd+K, and navigates on click.

(function () {
  if (window.__codexSearchLoaded) return;
  window.__codexSearchLoaded = true;

  const STYLE = `
    .codex-search-overlay {
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.6);
      z-index: 2147483647;
      display: flex; align-items: flex-start; justify-content: center;
      padding-top: 12vh;
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
    }
    .codex-search-box {
      width: 90%; max-width: 640px;
      background: #1a1a1a; color: #e5e5e5;
      border: 1px solid #2e2c28; border-radius: 8px;
      box-shadow: 0 16px 48px rgba(0,0,0,0.6);
      overflow: hidden;
    }
    .codex-search-input {
      width: 100%; padding: 14px 18px;
      background: transparent; border: 0; outline: none;
      color: #e5e5e5; font-size: 15px;
      border-bottom: 1px solid #2e2c28;
    }
    .codex-search-input::placeholder { color: #888; }
    .codex-search-results {
      max-height: 50vh; overflow-y: auto;
    }
    .codex-search-result {
      display: block; padding: 10px 18px;
      color: #e5e5e5; text-decoration: none;
      border-bottom: 1px solid #242220;
    }
    .codex-search-result:hover,
    .codex-search-result.active {
      background: #242220;
    }
    .codex-search-result-title {
      font-weight: 500; font-size: 14px;
    }
    .codex-search-result-meta {
      font-size: 12px; color: #888; margin-top: 2px;
    }
    .codex-search-empty {
      padding: 18px; color: #888; font-size: 13px; text-align: center;
    }
    .codex-search-footer {
      padding: 8px 18px; font-size: 11px; color: #666;
      border-top: 1px solid #2e2c28; display: flex; gap: 16px;
    }
    .codex-search-footer kbd {
      background: #242220; padding: 1px 5px; border-radius: 3px;
      font-family: 'IBM Plex Mono', monospace; font-size: 10px;
    }
  `;

  let entries = null;
  let modal = null;
  let activeIndex = 0;
  let resultEls = [];

  function sourceRoot() {
    const m = location.pathname.match(/^(\/sources\/[^/]+\/)/);
    return m ? m[1] : '/';
  }

  function loadIndex() {
    if (entries !== null) return Promise.resolve(entries);
    return fetch(sourceRoot() + '_codex_search.json', {cache: 'no-cache'})
      .then(r => (r.ok ? r.json() : []))
      .then(data => { entries = Array.isArray(data) ? data : []; })
      .catch(() => { entries = []; });
  }

  function score(entry, tokens) {
    const title = (entry.title || '').toLowerCase();
    const headings = (entry.headings || []).join(' ').toLowerCase();
    const snippet = (entry.snippet || '').toLowerCase();
    let s = 0;
    for (const t of tokens) {
      if (!t) continue;
      if (title.startsWith(t)) s += 30;
      if (title.includes(t)) s += 12;
      if (headings.includes(t)) s += 5;
      if (snippet.includes(t)) s += 1;
    }
    return s;
  }

  function search(q) {
    if (!entries || !q) return [];
    const tokens = q.toLowerCase().trim().split(/\s+/);
    if (tokens.length === 0) return [];
    return entries
      .map(e => ({ e, s: score(e, tokens) }))
      .filter(r => r.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 25)
      .map(r => r.e);
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  function build() {
    const style = document.createElement('style');
    style.textContent = STYLE;
    document.head.appendChild(style);

    const overlay = document.createElement('div');
    overlay.className = 'codex-search-overlay';
    overlay.innerHTML = `
      <div class="codex-search-box" role="dialog" aria-label="Search">
        <input class="codex-search-input" type="search" placeholder="Search this package…" autocomplete="off" spellcheck="false">
        <div class="codex-search-results"></div>
        <div class="codex-search-footer">
          <span><kbd>↑</kbd> <kbd>↓</kbd> navigate</span>
          <span><kbd>Enter</kbd> open</span>
          <span><kbd>Esc</kbd> close</span>
        </div>
      </div>
    `;
    const input = overlay.querySelector('input');
    const results = overlay.querySelector('.codex-search-results');

    function render(hits) {
      activeIndex = 0;
      if (!input.value.trim()) {
        results.innerHTML = '<div class="codex-search-empty">Type to search</div>';
        resultEls = [];
        return;
      }
      if (hits.length === 0) {
        results.innerHTML = '<div class="codex-search-empty">No results</div>';
        resultEls = [];
        return;
      }
      results.innerHTML = hits.map((h, i) => `
        <a class="codex-search-result${i === 0 ? ' active' : ''}" href="${esc(h.url)}" data-i="${i}">
          <div class="codex-search-result-title">${esc(h.title)}</div>
          ${h.snippet ? `<div class="codex-search-result-meta">${esc(h.snippet).slice(0, 140)}</div>` : ''}
        </a>
      `).join('');
      resultEls = Array.from(results.querySelectorAll('.codex-search-result'));
    }

    input.addEventListener('input', () => render(search(input.value)));

    overlay.addEventListener('click', e => {
      if (e.target === overlay) close();
    });

    overlay.addEventListener('keydown', e => {
      if (e.key === 'Escape') { close(); return; }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (resultEls.length === 0) return;
        e.preventDefault();
        resultEls[activeIndex] && resultEls[activeIndex].classList.remove('active');
        activeIndex = (activeIndex + (e.key === 'ArrowDown' ? 1 : -1) + resultEls.length) % resultEls.length;
        const el = resultEls[activeIndex];
        el.classList.add('active');
        el.scrollIntoView({block: 'nearest'});
        return;
      }
      if (e.key === 'Enter') {
        if (resultEls.length > 0) {
          resultEls[activeIndex].click();
        }
      }
    });

    document.body.appendChild(overlay);
    return overlay;
  }

  function open() {
    if (!modal) modal = build();
    modal.style.display = 'flex';
    const input = modal.querySelector('input');
    input.value = '';
    modal.querySelector('.codex-search-results').innerHTML =
      '<div class="codex-search-empty">Type to search</div>';
    input.focus();
    loadIndex();
  }

  function close() {
    if (modal) modal.style.display = 'none';
  }

  document.addEventListener('keydown', e => {
    const ck = (e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K');
    if (ck) {
      e.preventDefault();
      e.stopPropagation();
      if (modal && modal.style.display === 'flex') close(); else open();
    }
  }, true);

  // Hijack upstream search controls. React.dev / Next.js use Algolia's
  // widgets which are dead without API keys, so we intercept the click and
  // open the Codex modal instead.
  function isSearchEl(el) {
    const al = (el.getAttribute('aria-label') || '').toLowerCase();
    const ph = (el.getAttribute('placeholder') || '').toLowerCase();
    const cls = (el.className || '').toString().toLowerCase();
    if (al.includes('search') || ph.includes('search')) return true;
    if (cls.includes('search') || cls.includes('docsearch')) return true;
    // React.dev's desktop search button has no aria-label and no search-named
    // class — it's identifiable only by its visible text "Search" plus the
    // magnifying-glass SVG. Be conservative: only match when the button's
    // textContent starts with "Search" and is reasonably short.
    if (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') {
      const text = (el.textContent || '').trim();
      if (text.length > 0 && text.length < 60 && /^search\b/i.test(text)) {
        return true;
      }
      // Tailwind's desktop search button is a pill containing an SVG plus
      // two <kbd> elements showing "⌘K" / "Ctrl K". textContent collapses to
      // "⌘KCtrl K" (no separator between kbds), so no word boundary check —
      // just look for either shortcut substring.
      if (text.length > 0 && text.length < 30 && /(?:⌘k|ctrl ?k)/i.test(text)) {
        return true;
      }
    }
    return false;
  }

  function hookSearchButtons(root) {
    (root || document).querySelectorAll('button, input, [role="button"], [role="search"]').forEach(el => {
      if (el.dataset.codexHooked) return;
      if (!isSearchEl(el)) return;
      el.dataset.codexHooked = '1';
      el.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        open();
      }, true);
      if (el.tagName === 'INPUT') {
        el.addEventListener('focus', e => {
          e.preventDefault();
          el.blur();
          open();
        }, true);
      }
    });
  }

  // Next.js-specific: the App/Pages router toggle is a JS-driven dropdown.
  // The button is still in the DOM but its menu isn't. Hijack the click to
  // navigate directly to the parallel page under the other router.
  function hookNextjsRouterToggle(root) {
    const m = location.pathname.match(/^(\/sources\/nextjs\/)(app|pages)\/(.*?)\/?(?:index\.html)?$/);
    if (!m) return;
    const [, prefix, current, rest] = m;
    if (!rest) return;
    const other = current === 'app' ? 'pages' : 'app';
    const otherUrl = `${prefix}${other}/${rest}/`;

    const re = /Using (App|Pages) Router/i;
    const walker = document.createTreeWalker(root || document.body, NodeFilter.SHOW_TEXT);
    const hits = [];
    let node;
    while ((node = walker.nextNode())) {
      if (re.test(node.nodeValue || '')) hits.push(node);
    }
    hits.forEach(textNode => {
      let el = textNode.parentElement;
      let trigger = null;
      while (el && el !== document.body) {
        if (
          el.tagName === 'BUTTON' ||
          el.getAttribute('role') === 'button' ||
          el.getAttribute('role') === 'combobox' ||
          el.tagName === 'A'
        ) {
          trigger = el;
          break;
        }
        el = el.parentElement;
      }
      if (!trigger || trigger.dataset.codexRouterHooked) return;
      trigger.dataset.codexRouterHooked = '1';
      trigger.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        location.href = otherUrl;
      }, true);
    });
  }

  // Tailwind's sidebar nav surfaces promotional links (Components, Templates,
  // UI Kit, Playground, Course, Community) that go to tailwindui.com / external
  // sites — useless and broken offline. Keep only links into our docs subtree;
  // hide everything else (incl. the stager-rewritten /sources/tailwind/plus/…
  // paths that don't actually exist offline).
  function hookTailwindHideLinks(root) {
    if (!/^\/sources\/tailwind\//.test(location.pathname)) return;
    const docsPrefix = '/sources/tailwind/docs';
    (root || document).querySelectorAll('nav a[href]').forEach(a => {
      const href = a.getAttribute('href') || '';
      if (href.startsWith('#')) return;
      if (href.startsWith('./') || href.startsWith('../')) return;
      if (href.startsWith(docsPrefix)) return;
      const li = a.closest('li');
      (li || a).style.display = 'none';
    });
  }

  function initShims() {
    try { hookSearchButtons(); } catch (e) { console.warn('[codex]', e); }
    try { hookNextjsRouterToggle(); } catch (e) { console.warn('[codex]', e); }
    try { hookTailwindHideLinks(); } catch (e) { console.warn('[codex]', e); }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initShims);
  } else {
    initShims();
  }
})();
