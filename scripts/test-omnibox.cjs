const fs = require('fs');
const assert = require('assert/strict');
const path = require('path');
const os = require('os');
const repo = path.resolve(__dirname, '..');
const buildDir = fs.mkdtempSync(path.join(os.tmpdir(), 'peachjam-omnibox-test-'));
const webpack = require(`${repo}/node_modules/webpack`);
const puppeteer = require(`${repo}/node_modules/puppeteer`);
const config = require(`${repo}/webpack.config.js`)({}, { mode: 'development' })[0];
const entry = path.join(buildDir, 'entry.js');
fs.writeFileSync(entry, `export { default as peachJam } from ${JSON.stringify(repo + '/peachjam/js/peachjam.ts')};\nexport { default as SearchInput } from ${JSON.stringify(repo + '/peachjam/js/components/search-input.ts')};\nexport { default as htmx } from ${JSON.stringify(require.resolve('htmx.org'))};`);
config.context = repo;
config.entry = entry;
config.output = { path: buildDir, filename: 'omnibox.js', library: { name: 'OmniboxTest', type: 'window' } };
const build = () => new Promise((resolve, reject) => webpack(config, (error, stats) => {
  if (error || stats.hasErrors()) reject(error || new Error(stats.toString({ all: false, errors: true })));
  else resolve();
}));

(async () => {
  await build();
  const browser = await puppeteer.launch({ headless: true, executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || (fs.existsSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome') ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : undefined) });
  try {
    const page = await browser.newPage();
    const errors = [];
    const requests = [];
    let shortcutsFail = false;
    let suggestionsFail = false;
    let newlySaved = false;
    let rankingCase = false;
    let urlPrefix = '';
    let userDelay = 0;
    let holdUserResponse = false;
    let releaseUserResponse;
    let holdHistoryResponse = false;
    let releaseHistoryResponse;
    let historyFail = false;
    const historyItems = () => page.evaluate(() => window.omniboxSource.history.items);
    const waitForHistory = () => page.evaluate(() => window.omniboxSource.historyUpdates);
    const accountHistory = new Map();
    const historyKey = value => {
      const url = new URL(value, 'http://omnibox.test');
      for (const key of ['suggestion', 'gsc.tab']) url.searchParams.delete(key);
      for (const [key, value] of [['page', '1'], ['ordering', '-score'], ['mode', 'text']]) {
        if (url.searchParams.get(key) === value) url.searchParams.delete(key);
      }
      if (url.searchParams.has('q')) url.searchParams.set('q', url.searchParams.get('q').trim().replace(/\s+/g, ' ').toLowerCase());
      url.searchParams.sort();
      return url.searchParams.toString();
    };
    const historyData = () => {
      const fallback = { id: 'recent', type: 'history', text: 'contract law', url: '/search/?q=contract+law&court=high-court' };
      const items = [...accountHistory.values()].reverse();
      if (!accountHistory.has(historyKey(fallback.url))) items.push(fallback);
      return { recent_searches: items.filter(item => !item.removed) };
    };
    page.on('pageerror', error => { errors.push(error.message); console.error(error); });
    await page.setRequestInterception(true);
    const css = fs.readFileSync(`${repo}/node_modules/bootstrap/dist/css/bootstrap.css`, 'utf8');
    const html = `<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style></head><body><main class="container py-5">
      <h1>Omnibox preview</h1><form id="form" action="/search/"><input type="hidden" name="suggestion"><input id="anchor" name="q" class="form-control" aria-label="Search documents" placeholder="Search"><button>Search</button></form>
      <input id="second" aria-label="Second search"><button id="outside">Outside control</button></main>
      <script src="/omnibox.js"></script><script>
      const {SearchInput, peachJam, htmx} = window.OmniboxTest;
      window.peachjam = peachJam;
      window.htmx = htmx;
      document.cookie = 'csrftoken=local-test-token; path=/';
      peachJam.config.urlLangPrefix = location.pathname.startsWith('/fr/') ? '/fr' : '';
      window.SearchInput = SearchInput;
      window.submissions=[];
      document.querySelector('#form').addEventListener('submit', e => {e.preventDefault(); window.submissions.push({query:e.target.q.value,suggestion:e.target.suggestion.value});});
      new SearchInput(document.querySelector('#anchor'));
      new SearchInput(document.querySelector('#second'), {onSearch: (query,suggestion) => window.submissions.push({query,suggestion})});
      window.omniboxSource = document.querySelector('dialog').__vueParentComponent.parent.ctx.suggestionSource;
      window.userLoad = peachJam.loaded();
      </script></body></html>`;
    page.on('request', request => {
      const url = new URL(request.url());
      requests.push(url.pathname);
      if (url.pathname === '/omnibox.js') return request.respond({ contentType: 'application/javascript', body: fs.readFileSync(path.join(buildDir, 'omnibox.js'), 'utf8') });
      if (url.pathname === `${urlPrefix}/user/search-history`) {
        if (historyFail) return request.respond({ status: 503, body: 'Unavailable' });
        const body = new URLSearchParams(request.postData());
        const key = historyKey(body.get('url'));
        accountHistory.delete(key);
        accountHistory.set(key, { id: `history-${key}`, type: 'history', text: body.get('text'), url: body.get('url'), removed: body.get('action') === 'remove' });
        const bodyText = JSON.stringify(historyData());
        const respond = () => request.respond({ contentType: 'application/json', body: bodyText });
        if (holdHistoryResponse) {
          releaseHistoryResponse = respond;
          return;
        }
        return respond();
      }
      if (url.pathname === `${urlPrefix}/user/loaded`) {
        const shortcuts = {
          user_id: 7,
          ...historyData(),
          saved_items: rankingCase ? [
            ...Array.from({ length: 8 }, (_, index) => ({ id: `document-${index}`, type: 'document', work_id: index, text: `A law document ${index}`, url: `/document/${index}/` })),
            { id: 'folder-2', type: 'folder', text: 'Law', url: '/my/folders/#folder-2' },
            { id: 'search-2', type: 'saved_search', text: 'Law alerts', url: '/search/?q=law' }
          ] : [
            { id: 'document-1', type: 'document', work_id: 101, text: 'Contract Act', url: '/document/contract/' },
            { id: 'folder-1', type: 'folder', text: 'Contract research', url: '/my/folders/#folder-1' },
            { id: 'search-1', type: 'saved_search', text: 'Contracts in 2025', url: '/search/?q=contracts&year=2025' },
            ...(newlySaved ? [{ id: 'document-2', type: 'document', work_id: 2, text: 'New saved document', url: '/document/new/' }] : [])]
        };
        const respond = () => request.respond({
          status: shortcutsFail ? 503 : 200,
          contentType: 'text/html',
          body: `<script>peachjam.user = JSON.parse(${JSON.stringify(JSON.stringify({ id: 7, perms: [], omnibox: shortcuts }))}); peachjam.userLoaded();</script>`
        });
        if (holdUserResponse) {
          releaseUserResponse = respond;
          return;
        }
        return setTimeout(respond, userDelay);
      }
      if (url.pathname === `${urlPrefix}/search/api/documents/suggest/`) return request.respond({ status: suggestionsFail ? 503 : 200, contentType: 'application/json', body: JSON.stringify({ suggestions: [{ value: url.searchParams.get('q') + ' law', type: 'title', type_label: 'Document title' }] }) });
      if (url.pathname === '/document/contract/') return request.respond({ contentType: 'text/html', body: '<h1>Document opened</h1>' });
      if (url.pathname === '/document/ordinary/') return request.respond({ contentType: 'text/html', body: html.replace('<h1>Omnibox preview</h1>', '<h1>Document page</h1><div id="document-content" data-work-id="101" data-document-id="202"></div>') });
      if (url.pathname === '/document/different-work/') return request.respond({ contentType: 'text/html', body: html.replace('<h1>Omnibox preview</h1>', '<h1>Other work</h1><div id="document-content" data-work-id="999" data-document-id="101"></div>') });
      if (url.pathname === '/my/folders/') return request.respond({ contentType: 'text/html', body: html.replace('<h1>Omnibox preview</h1>', '<h1>Saved folders</h1><div id="folder-1">Contract research</div>') });
      return request.respond({ contentType: 'text/html', body: html });
    });
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto('http://omnibox.test/');
    await page.waitForFunction(() => window.SearchInput);
    assert.equal(await page.$eval('dialog', el => el.open), false);
    await page.click('#anchor');
    await page.waitForSelector('#omnibox-history');
    assert.equal(await page.$$('dialog .badge').then(items => items.length), 0);
    assert.equal(requests.filter(path => path === '/user/loaded').length, 1);
    assert.equal(requests.filter(path => path === '/search/api/omnibox/').length, 0);
    assert.equal(await page.$eval('dialog input', el => document.activeElement === el), true);
    assert.equal(await page.$eval('dialog', el => el.matches(':modal')), false);
    const desktopInput = await page.$eval('dialog input', el => ({ border: getComputedStyle(el).borderTopWidth, shadow: getComputedStyle(el).boxShadow }));
    assert.deepEqual(desktopInput, { border: '0px', shadow: 'none' });
    assert.equal(await page.$eval('dialog button[type="submit"] span', el => getComputedStyle(el).display === 'none'), false);
    assert.equal(await page.$eval('#form', el => getComputedStyle(el).visibility), 'hidden');
    await page.keyboard.press('ArrowDown');
    assert.match(await page.evaluate(() => document.activeElement.href), /court=high-court/);
    await page.keyboard.press('Escape');
    assert.equal(await page.$eval('dialog', el => el.open), false);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'anchor');
    assert.equal(await page.$eval('#form', el => getComputedStyle(el).visibility), 'visible');
    await page.click('#anchor');
    await page.type('dialog input', 'contract');
    await page.waitForSelector('#omnibox-suggestions');
    const headings = await page.$$eval('dialog h3', els => els.map(el => el.textContent.trim()));
    assert.deepEqual(headings, ['Recent searches', 'Saved searches', 'Saved items', 'Search suggestions']);
    const rowLayout = await page.evaluate(() => {
      const geometry = selector => {
        const row = document.querySelector(selector);
        const icon = row.querySelector('.search-box__icon').getBoundingClientRect();
        const text = row.querySelector('span').getBoundingClientRect();
        return { iconLeft: icon.left, iconWidth: icon.width, textLeft: text.left, iconInset: icon.left - row.getBoundingClientRect().left };
      };
      return {
        saved: geometry('#omnibox-saved + ul a'),
        suggestion: geometry('#omnibox-suggestions + ul button')
      };
    });
    assert.deepEqual(rowLayout.saved, rowLayout.suggestion);
    assert.ok(rowLayout.saved.iconInset >= 12);
    assert.ok(await page.$$('dialog .badge').then(items => items.length > 0));
    await page.keyboard.press('ArrowDown');
    const savedHighlight = await page.evaluate(() => getComputedStyle(document.activeElement.closest('li')).backgroundColor);
    await page.$eval('#omnibox-suggestions + ul button', el => el.focus());
    const suggestionHighlight = await page.evaluate(() => getComputedStyle(document.activeElement.closest('li')).backgroundColor);
    assert.equal(savedHighlight, 'rgb(248, 249, 250)');
    assert.equal(suggestionHighlight, savedHighlight);
    await page.click('#omnibox-suggestions + ul button');
    assert.deepEqual(await page.evaluate(() => window.submissions), [{ query: 'contract law', suggestion: 'title' }]);
    assert.equal(await page.$eval('dialog', el => el.open), false);
    await page.click('#anchor');
    await page.$eval('dialog input', el => { el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForSelector('#omnibox-document + ul a');
    await page.click('#omnibox-document + ul a');
    await page.waitForSelector('h1');
    assert.match(page.url(), /document\/contract/);
    assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('peachjam.omnibox.7'))), ['document-1']);
    await page.evaluate(() => localStorage.removeItem('peachjam.omnibox.7'));
    await page.goto('http://omnibox.test/document/ordinary/');
    await page.waitForFunction(() => JSON.parse(localStorage.getItem('peachjam.omnibox.7') || '[]').includes('document-1'));
    await page.evaluate(() => localStorage.removeItem('peachjam.omnibox.7'));
    await page.goto('http://omnibox.test/document/different-work/');
    await page.evaluate(() => window.userLoad);
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('peachjam.omnibox.7') || '[]').includes('document-1')), false);
    await page.goto('http://omnibox.test/my/folders/');
    await page.evaluate(() => window.userLoad);
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('peachjam.omnibox.7') || '[]').includes('folder-1')), false);
    await page.evaluate(() => { window.location.hash = 'folder-1'; });
    await page.waitForFunction(() => JSON.parse(localStorage.getItem('peachjam.omnibox.7') || '[]').includes('folder-1'));
    await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
    await page.goto('http://omnibox.test/');
    await page.click('#anchor');
    await page.waitForSelector('#omnibox-history');
    const rect = await page.$eval('dialog', el => ({ width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height, innerWidth, innerHeight }));
    assert.equal(rect.width, rect.innerWidth);
    assert.equal(rect.height, rect.innerHeight);
    assert.equal(await page.$eval('dialog', el => el.matches(':modal')), true);
    assert.equal(await page.$eval('dialog button[type="submit"] span', el => getComputedStyle(el).display), 'none');
    assert.equal(await page.$eval('dialog button[type="submit"] i', el => getComputedStyle(el).display === 'none'), false);
    assert.equal(await page.$eval('dialog button[type="submit"]', el => el.getAttribute('aria-label')), 'Search');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => !!document.activeElement.closest('dialog')), true);

    await page.click('dialog .btn-close');
    assert.equal(await page.$eval('dialog', el => el.open), false);
    await page.setViewport({ width: 1280, height: 900 });
    await page.click('#second');
    await page.type('dialog input', 'custom query');
    await page.keyboard.press('Enter');
    assert.deepEqual(await page.evaluate(() => window.submissions), [{ query: 'custom query', suggestion: null }]);
    await page.click('#second');
    await page.mouse.click(1250, 880);
    assert.equal(await page.$eval('dialog', el => el.open), false);
    newlySaved = true;
    await page.evaluate(() => document.dispatchEvent(new CustomEvent('htmx:afterRequest', {
      detail: { successful: true, requestConfig: { verb: 'post', path: '/user/saved-documents/create?doc_id=2' } }
    })));
    await page.click('#second');
    await page.$eval('dialog input', el => { el.value = 'New saved'; el.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForFunction(() => Array.from(document.querySelectorAll('dialog a')).some(el => el.textContent.includes('New saved document')));
    await page.keyboard.press('Escape');
    // Changes during a slow refresh must produce one later refresh, never an overlapping stale response.
    newlySaved = false;
    holdUserResponse = true;
    const refreshCount = requests.filter(path => path === '/user/loaded').length;
    const olderRefresh = page.waitForRequest(request => new URL(request.url()).pathname === '/user/loaded');
    await page.evaluate(() => { window.userRefresh = window.peachjam.loaded(); });
    await olderRefresh;
    newlySaved = true;
    await page.evaluate(() => {
      for (const path of ['/user/saved-documents/create?doc_id=2', '/my/folders/1/update']) {
        document.dispatchEvent(new CustomEvent('htmx:afterRequest', {
          detail: { successful: true, requestConfig: { verb: 'post', path } }
        }));
      }
    });
    assert.equal(requests.filter(path => path === '/user/loaded').length, refreshCount + 1);
    holdUserResponse = false;
    const followUp = page.waitForRequest(request => new URL(request.url()).pathname === '/user/loaded');
    await releaseUserResponse();
    await followUp;
    await page.evaluate(() => window.userRefresh);
    assert.equal(requests.filter(path => path === '/user/loaded').length, refreshCount + 2);
    assert.equal(await page.evaluate(() => window.peachjam.user.omnibox.saved_items.some(item => item.id === 'document-2')), true);

    // Cached results still produce personal history without changing the server's trace list.
    await page.evaluate(() => {
      const completed = (query, url) => window.dispatchEvent(new CustomEvent('peachjam.search-completed', { detail: { query, url } }));
      completed('Cached query', '/search/?q=Cached+query&suggestion=title');
      completed('Other query', '/search/?q=Other+query');
      completed('Cached query', '/search/?q=Cached+query&page=1');
    });
    await waitForHistory();
    assert.deepEqual((await historyItems()).map(item => item.text), ['Cached query', 'Other query', 'contract law']);
    assert.equal(await page.evaluate(() => localStorage.getItem('peachjam.omnibox.searches.7')), null);
    await page.click('#second');
    await page.$eval('dialog input', el => { el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForFunction(() => document.querySelector('#omnibox-history + ul a')?.textContent.includes('Cached query'));

    // Each control has its own visible keyboard focus, including the remove button.
    await page.keyboard.press('ArrowDown');
    const resultFocus = await page.evaluate(() => getComputedStyle(document.activeElement).boxShadow);
    assert.notEqual(resultFocus, 'none');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.classList.contains('search-box__remove')), true);
    assert.notEqual(await page.evaluate(() => getComputedStyle(document.activeElement).boxShadow), 'none');

    // A user-menu response captured before a removal must not restore the entry.
    holdUserResponse = true;
    const staleRefresh = page.waitForRequest(request => new URL(request.url()).pathname === '/user/loaded');
    await page.evaluate(() => { window.userRefresh = window.peachjam.loaded(); });
    await staleRefresh;
    await page.$eval('#omnibox-history + ul button[aria-label="Remove recent search: contract law"]', el => el.focus());
    await page.keyboard.press('Enter');
    await waitForHistory();
    await page.waitForFunction(() => !document.querySelector('button[aria-label="Remove recent search: contract law"]'));
    assert.equal(await page.$eval('dialog', el => el.open), true);
    assert.equal(await page.evaluate(() => !!document.activeElement.closest('dialog')), true);
    holdUserResponse = false;
    await releaseUserResponse();
    await page.evaluate(() => window.userRefresh);
    assert.equal((await historyItems()).some(item => item.text === 'contract law'), false);

    await page.click('#omnibox-history + ul button[aria-label="Remove recent search: Cached query"]');
    await waitForHistory();
    assert.deepEqual((await historyItems()).map(item => item.text), ['Other query']);
    await page.goto('http://omnibox.test/');
    await page.click('#second');
    await page.waitForSelector('#omnibox-document');
    const recentNames = await page.$$eval('#omnibox-history + ul a', links => links.map(link => link.textContent.trim()));
    assert.deepEqual(recentNames, ['Other query']);

    // Failed removals preserve the confirmed list and the focused remove button.
    historyFail = true;
    await page.$eval('#omnibox-history + ul button', el => el.focus());
    await page.keyboard.press('Enter');
    await waitForHistory();
    assert.deepEqual((await historyItems()).map(item => item.text), ['Other query']);
    assert.equal(await page.evaluate(() => document.activeElement.classList.contains('search-box__remove')), true);
    historyFail = false;

    // A failed queued write must not discard an earlier confirmed removal.
    holdHistoryResponse = true;
    const confirmedRemoval = page.waitForRequest(request => new URL(request.url()).pathname === '/user/search-history');
    await page.click('#omnibox-history + ul button[aria-label="Remove recent search: Other query"]');
    await confirmedRemoval;
    historyFail = true;
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('peachjam.search-completed', {
      detail: { query: 'Failed queued query', url: '/search/?q=failed-queued' }
    })));
    holdHistoryResponse = false;
    await releaseHistoryResponse();
    await waitForHistory();
    assert.deepEqual(await historyItems(), []);
    assert.equal(await page.$('#omnibox-history'), null);
    assert.equal(await page.evaluate(() => !!document.activeElement.closest('dialog')), true);
    historyFail = false;
    await page.keyboard.press('Escape');

    // History writes retain the original replay URL, including capitalization and spacing.
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('peachjam.search-completed', {
      detail: { query: 'Foo AND Bar', url: '/search/?q=Foo+AND++Bar&court=high-court' }
    })));
    await waitForHistory();
    assert.equal((await historyItems())[0].url, '/search/?q=Foo+AND++Bar&court=high-court');

    // An in-flight response must not populate a different user's history.
    holdHistoryResponse = true;
    const pendingHistory = page.waitForRequest(request => new URL(request.url()).pathname === '/user/search-history');
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('peachjam.search-completed', {
      detail: { query: 'Private query', url: '/search/?q=private' }
    })));
    await pendingHistory;
    await page.evaluate(() => {
      window.peachjam.user.omnibox = { user_id: 8, recent_searches: [], saved_items: [] };
      window.peachjam.userLoaded();
    });
    assert.deepEqual(await historyItems(), []);
    // Even signing back into the original account must invalidate its old response.
    await page.evaluate(() => {
      window.peachjam.user.omnibox = { user_id: 7, recent_searches: [], saved_items: [] };
      window.peachjam.userLoaded();
    });
    holdHistoryResponse = false;
    await releaseHistoryResponse();
    await waitForHistory();
    assert.deepEqual(await historyItems(), []);
    const historyRequestCount = requests.filter(path => path === '/user/search-history').length;
    await page.evaluate(() => {
      window.peachjam.user.omnibox = { user_id: null, recent_searches: [], saved_items: [] };
      window.peachjam.userLoaded();
      window.dispatchEvent(new CustomEvent('peachjam.search-completed', {
        detail: { query: 'Anonymous query', url: '/search/?q=anonymous' }
      }));
    });
    await waitForHistory();
    assert.equal(requests.filter(path => path === '/user/search-history').length, historyRequestCount);
    assert.deepEqual(await historyItems(), []);
    rankingCase = true;
    await page.evaluate(() => document.dispatchEvent(new CustomEvent('htmx:afterRequest', {
      detail: { successful: true, requestConfig: { verb: 'post', path: '/my/folders/create' } }
    })));
    await page.click('#second');
    await page.$eval('dialog input', el => { el.value = 'law'; el.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForFunction(() => document.querySelector('#omnibox-saved + ul a')?.getAttribute('href') === '/my/folders/#folder-2');
    const ranked = await page.$$eval('#omnibox-saved + ul a', links => links.map(link => link.getAttribute('href')));
    assert.equal(ranked.length, 8);
    assert.equal(await page.$eval('#omnibox-saved_search + ul a', el => el.getAttribute('href')), '/search/?q=law');
    await page.keyboard.press('Escape');

    // Show only three recent entries, then filter the full history as the user types.
    await page.evaluate(() => {
      for (let index = 0; index < 5; index++) {
        window.dispatchEvent(new CustomEvent('peachjam.search-completed', {
          detail: { query: `Research ${index}`, url: `/search/?q=research-${index}` }
        }));
      }
    });
    await waitForHistory();
    await page.click('#anchor');
    await page.$eval('dialog input', el => { el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForFunction(() => document.querySelectorAll('#omnibox-history + ul a').length === 3);
    assert.deepEqual(await page.$$eval('#omnibox-history + ul a', links => links.map(link => link.textContent.trim())), ['Research 4', 'Research 3', 'Research 2']);
    assert.deepEqual((await page.$$eval('dialog h3', els => els.map(el => el.textContent.trim()))).slice(0, 2), ['Recent searches', 'Saved searches']);
    await page.type('dialog input', 'RESEARCH 0');
    await page.waitForFunction(() => document.querySelector('#omnibox-history + ul a')?.textContent.includes('Research 0'));
    assert.equal(await page.$('#omnibox-saved_search'), null);
    await page.$eval('dialog input', el => { el.value = 'law'; el.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForSelector('#omnibox-saved_search + ul a');
    assert.equal(await page.$('#omnibox-history'), null);
    assert.equal(await page.$eval('#omnibox-saved_search + ul a', el => el.textContent.trim()), 'Law alerts');
    await page.keyboard.press('Escape');
    shortcutsFail = true;
    suggestionsFail = true;
    await page.goto('http://omnibox.test/');
    await page.click('#anchor');
    await page.evaluate(() => window.userLoad);
    assert.equal(await page.$$('dialog section').then(items => items.length), 0);
    assert.equal(await page.$$('dialog p').then(items => items.length), 0);
    const historyRequestCountBeforeLoad = requests.filter(path => path.endsWith('/user/search-history')).length;
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('peachjam.search-completed', {
      detail: { query: 'Unknown user', url: '/search/?q=unknown' }
    })));
    assert.equal(requests.filter(path => path.endsWith('/user/search-history')).length, historyRequestCountBeforeLoad);
    const failedSuggestion = page.waitForResponse(response => response.url().includes('/documents/suggest/'));
    await page.type('dialog input', 'failed suggestion');
    await (await failedSuggestion).text();
    assert.equal(await page.$$('dialog section').then(items => items.length), 0);
    assert.equal(await page.$$('dialog p').then(items => items.length), 0);
    await page.keyboard.press('Enter');
    assert.equal(await page.$eval('dialog', el => el.open), false);
    // User loading may finish after the first search; both URLs must respect language prefixes.
    shortcutsFail = false;
    suggestionsFail = false;
    urlPrefix = '/fr';
    userDelay = 500;
    await page.goto('http://omnibox.test/fr/');
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('peachjam.search-completed', {
      detail: { query: 'Early search', url: '/fr/search/?q=early' }
    })));
    await page.click('#anchor');
    await page.waitForSelector('#omnibox-document');
    await page.waitForFunction(() => window.omniboxSource.history.items.some(item => item.text === 'Early search'));
    await page.type('dialog input', 'law');
    await page.waitForSelector('#omnibox-suggestions');
    assert.equal(requests.filter(path => path === '/fr/user/loaded').length, 1);
    assert.ok(requests.includes('/fr/search/api/documents/suggest/'));
    assert.deepEqual(errors, []);
    console.log('PASS: persistent recent-search removal, consistent row alignment and focus, cached-search history, user isolation, ranking, serialized refreshes, mobile layout, keyboard support and failure fallback.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => fs.rmSync(buildDir, { recursive: true, force: true }));
