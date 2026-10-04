// Acceptance tests for ticket #7: app.js binds live search and My Cookbook toggles to the DOM.
// A tiny in-memory DOM is installed on globalThis before app.js is imported, so no browser is needed.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const APP_URL = new URL('../app.js', import.meta.url);
const EMPTY = 'No recipes found. Try another ingredient or dish.';
const ERROR = 'Could not update My Cookbook. Please try again.';

// ---------- minimal DOM ----------
const kebab = (s) => s.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);

function parseCompound(src) {
  const out = {tag: null, id: null, classes: [], attrs: []};
  const re = /([a-zA-Z][\w-]*)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:=["']?([^\]"']*)["']?)?\]/y;
  let m;
  re.lastIndex = 0;
  while (re.lastIndex < src.length && (m = re.exec(src))) {
    if (m[1]) out.tag = m[1].toLowerCase();
    else if (m[2]) out.id = m[2];
    else if (m[3]) out.classes.push(m[3]);
    else out.attrs.push([m[4], m[5]]);
  }
  return out;
}

class El {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = doc;
    this.attrs = new Map();
    this.children = [];
    this.parentNode = null;
    this.listeners = {};
    this._text = '';
    this.value = '';
    const self = this;
    this.dataset = new Proxy({}, {
      get: (_, p) => (typeof p === 'string' ? self.attrs.get(`data-${kebab(p)}`) : undefined),
      set: (_, p, v) => { self.attrs.set(`data-${kebab(p)}`, String(v)); return true; },
    });
    const list = () => (self.attrs.get('class') || '').split(/\s+/).filter(Boolean);
    const save = (l) => self.attrs.set('class', l.join(' '));
    this.classList = {
      add: (...n) => save([...new Set([...list(), ...n])]),
      remove: (...n) => save(list().filter((c) => !n.includes(c))),
      contains: (n) => list().includes(n),
      toggle: (n, force) => {
        const on = force === undefined ? !list().includes(n) : Boolean(force);
        save(on ? [...new Set([...list(), n])] : list().filter((c) => c !== n));
        return on;
      },
    };
  }
  get id() { return this.attrs.get('id') ?? ''; }
  set id(v) { this.attrs.set('id', String(v)); }
  get className() { return this.attrs.get('class') ?? ''; }
  set className(v) { this.attrs.set('class', String(v)); }
  get hidden() { return this.attrs.has('hidden'); }
  set hidden(v) { if (v) this.attrs.set('hidden', ''); else this.attrs.delete('hidden'); }
  get disabled() { return this.attrs.has('disabled'); }
  set disabled(v) { if (v) this.attrs.set('disabled', ''); else this.attrs.delete('disabled'); }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  set textContent(v) {
    this.children.forEach((c) => { c.parentNode = null; });
    this.children = [];
    this._text = String(v);
  }
  get innerText() { return this.textContent; }
  set innerText(v) { this.textContent = v; }
  get parentElement() { return this.parentNode; }
  setAttribute(n, v) { this.attrs.set(n, String(v)); }
  getAttribute(n) { return this.attrs.has(n) ? this.attrs.get(n) : null; }
  hasAttribute(n) { return this.attrs.has(n); }
  removeAttribute(n) { this.attrs.delete(n); }
  appendChild(c) {
    if (c.parentNode) c.parentNode.children = c.parentNode.children.filter((x) => x !== c);
    c.parentNode = this;
    this.children.push(c);
    return c;
  }
  append(...cs) {
    cs.forEach((c) => {
      if (typeof c === 'string') {
        const t = new El('span', this.ownerDocument);
        t._text = c;
        this.appendChild(t);
      } else this.appendChild(c);
    });
  }
  focus() {}
  blur() {}
  addEventListener(t, fn) { (this.listeners[t] ||= []).push(fn); }
  removeEventListener(t, fn) { this.listeners[t] = (this.listeners[t] || []).filter((f) => f !== fn); }
  dispatchEvent(ev) {
    ev.target ||= this;
    ev.defaultPrevented = false;
    ev.preventDefault = () => { ev.defaultPrevented = true; };
    ev.stopPropagation = () => { ev.stopped = true; };
    for (let n = this; n && !ev.stopped; n = n.parentNode || (n.tagName === 'HTML' ? n.ownerDocument : null)) {
      ev.currentTarget = n;
      for (const fn of [...(n.listeners?.[ev.type] || [])]) fn.call(n, ev);
    }
    return !ev.defaultPrevented;
  }
  click() { return this.dispatchEvent({type: 'click', bubbles: true}); }
  matches(sel) {
    return sel.split(',').some((part) => {
      const chain = part.trim().split(/\s+/).map(parseCompound);
      const last = chain.pop();
      if (!this._matchOne(last)) return false;
      let node = this.parentNode;
      while (chain.length && node) {
        if (node._matchOne(chain[chain.length - 1])) chain.pop();
        node = node.parentNode;
      }
      return chain.length === 0;
    });
  }
  _matchOne(c) {
    if (c.tag && this.tagName.toLowerCase() !== c.tag) return false;
    if (c.id && this.id !== c.id) return false;
    if (!c.classes.every((k) => this.classList.contains(k))) return false;
    return c.attrs.every(([n, v]) => this.attrs.has(n) && (v === undefined || this.attrs.get(n) === v));
  }
  closest(sel) {
    for (let n = this; n; n = n.parentNode) if (n.matches?.(sel)) return n;
    return null;
  }
  contains(o) {
    for (let n = o; n; n = n.parentNode) if (n === this) return true;
    return false;
  }
  all() { return this.children.flatMap((c) => [c, ...c.all()]); }
  querySelectorAll(sel) { return this.all().filter((e) => e.matches(sel)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] ?? null; }
}

function h(doc, tag, attrs = {}, kids = [], text = '') {
  const el = new El(tag, doc);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v === true ? '' : v);
  el._text = text;
  kids.forEach((k) => el.appendChild(k));
  return el;
}

function makeDocument() {
  const doc = new El('#document', null);
  doc.ownerDocument = doc;
  doc.readyState = 'complete';
  doc.documentElement = new El('html', doc);
  doc.body = new El('body', doc);
  doc.appendChild(doc.documentElement);
  doc.documentElement.appendChild(doc.body);
  doc.createElement = (tag) => new El(tag, doc);
  doc.getElementById = (id) => doc.querySelector(`#${id}`);
  doc.activeElement = doc.body;
  return doc;
}

const RECIPES = [
  {id: 'lentil-soup', title: 'Red Lentil Soup', search: 'red lentil soup warming bowl dinner vegan red lentils carrot cumin'},
  {id: 'banana-pancakes', title: 'Banana Pancakes', search: 'banana pancakes fluffy breakfast vegetarian ripe banana flour milk'},
  {id: 'tomato-pasta', title: 'Tomato Basil Pasta', search: 'tomato basil pasta quick dinner vegetarian spaghetti garlic basil'},
];

function toggle(doc, r, saved, action) {
  const attrs = {
    type: 'button',
    class: `cookbook-toggle${saved ? ' saved' : ''}`,
    'data-recipe-id': r.id,
    'data-recipe-title': r.title,
    'aria-pressed': saved ? 'true' : 'false',
    'aria-label': saved ? `Remove ${r.title} from My Cookbook` : `Save ${r.title} to My Cookbook`,
  };
  if (action) attrs['data-action'] = action;
  return h(doc, 'button', attrs, [
    h(doc, 'span', {class: 'toggle-icon', 'aria-hidden': 'true'}, [], saved ? '✓' : '+'),
    h(doc, 'span', {class: 'toggle-text'}, [], saved ? 'Saved' : 'Save'),
  ]);
}

function browseDom(savedIds = []) {
  const doc = makeDocument();
  const input = h(doc, 'input', {id: 'search', type: 'search'});
  const count = h(doc, 'span', {id: 'count', role: 'status', 'aria-live': 'polite'}, [], `${RECIPES.length} recipes`);
  const grid = h(doc, 'section', {id: 'recipe-grid'}, RECIPES.map((r) =>
    h(doc, 'article', {class: 'recipe-card', 'data-recipe-id': r.id, 'data-search': r.search}, [
      h(doc, 'a', {href: `/recipe/${r.id}`}, [], r.title),
      toggle(doc, r, savedIds.includes(r.id)),
    ])));
  const empty = h(doc, 'p', {id: 'empty', class: 'empty', hidden: true}, [], EMPTY);
  [input, count, grid, empty].forEach((e) => doc.body.appendChild(e));
  return {doc, input, count, grid, empty, cards: grid.children, buttons: doc.querySelectorAll('.cookbook-toggle')};
}

function detailDom(saved = false) {
  const doc = makeDocument();
  const r = RECIPES[0];
  const back = h(doc, 'a', {class: 'back', 'data-action': 'back', href: '/'}, [], '← Browse recipes');
  const btn = toggle(doc, r, saved, 'cookbook');
  doc.body.appendChild(back);
  doc.body.appendChild(btn);
  return {doc, btn, back, recipe: r};
}

// ---------- harness ----------
let loadCount = 0;
const original = {document: globalThis.document, fetch: globalThis.fetch, window: globalThis.window};

async function settle() {
  for (let i = 0; i < 6; i += 1) await new Promise((r) => setTimeout(r, 0));
}

async function mount(doc, responder = () => ({ok: true, status: 200, body: {recipe_ids: []}})) {
  const calls = [];
  globalThis.document = doc;
  globalThis.window = {document: doc, location: {href: 'http://localhost/', assign() {}}, addEventListener() {}};
  globalThis.fetch = async (url, init = {}) => {
    const call = {url: String(url), method: (init.method || 'GET').toUpperCase(), body: init.body, headers: init.headers};
    calls.push(call);
    const r = responder(call);
    if (r instanceof Error) throw r;
    return {ok: r.ok, status: r.status, json: async () => r.body ?? {}, text: async () => JSON.stringify(r.body ?? {})};
  };
  try {
    await import(`${APP_URL.href}?run=${++loadCount}`);
  } catch (error) {
    assert.fail(`app.js must load against the recipe client logic and bind the DOM: ${error.message}`);
  }
  await settle();
  return calls;
}

test.afterEach(() => {
  globalThis.document = original.document;
  globalThis.fetch = original.fetch;
  globalThis.window = original.window;
});

function type(dom, value) {
  dom.input.value = value;
  dom.input.dispatchEvent({type: 'input', bubbles: true});
}

const visibleIds = (dom) => dom.cards.filter((c) => !c.hidden).map((c) => c.dataset.recipeId);

function statusText(doc) {
  return doc.querySelectorAll('[role=status], [aria-live=polite]').map((e) => e.textContent).join(' | ');
}

// ---------- live search ----------
test('typing an ingredient hides non-matching cards and updates the count without fetching', async () => {
  const dom = browseDom();
  const calls = await mount(dom.doc);
  type(dom, 'lentil');
  assert.deepEqual(visibleIds(dom), ['lentil-soup']);
  assert.equal(dom.count.textContent.trim(), '1 recipe');
  assert.equal(dom.empty.hidden, true);
  assert.deepEqual(calls, [], 'live search must not call the network');
});

test('search is case-insensitive, trims the query and can match several cards', async () => {
  const dom = browseDom();
  await mount(dom.doc);
  type(dom, '  VEGETARIAN ');
  assert.deepEqual(visibleIds(dom), ['banana-pancakes', 'tomato-pasta']);
  assert.equal(dom.count.textContent.trim(), '2 recipes');
});

test('clearing the query restores every card and the full count', async () => {
  const dom = browseDom();
  await mount(dom.doc);
  type(dom, 'banana');
  assert.deepEqual(visibleIds(dom), ['banana-pancakes']);
  type(dom, '');
  assert.deepEqual(visibleIds(dom), RECIPES.map((r) => r.id));
  assert.equal(dom.count.textContent.trim(), '3 recipes');
  assert.equal(dom.empty.hidden, true);
});

test('zero matches shows the exact empty message and a zero count', async () => {
  const dom = browseDom();
  await mount(dom.doc);
  type(dom, 'zzz-no-such-ingredient');
  assert.deepEqual(visibleIds(dom), []);
  assert.equal(dom.empty.hidden, false);
  assert.equal(dom.empty.textContent.trim(), EMPTY);
  assert.equal(dom.count.textContent.trim(), '0 recipes');
  type(dom, 'pasta');
  assert.equal(dom.empty.hidden, true);
  assert.equal(dom.count.textContent.trim(), '1 recipe');
});

test('search wiring is a no-op when #search is absent', async () => {
  const {doc, btn} = detailDom();
  await assert.doesNotReject(mount(doc));
  assert.equal(btn.getAttribute('aria-pressed'), 'false');
});

// ---------- My Cookbook toggles on cards ----------
test('saving a card POSTs {id} to /api/cookbook and updates text, icon, label, pressed and .saved', async () => {
  const dom = browseDom();
  const calls = await mount(dom.doc, () => ({ok: true, status: 201, body: {recipe_ids: ['banana-pancakes']}}));
  const btn = dom.buttons[1];
  btn.click();
  await settle();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/cookbook');
  assert.equal(calls[0].method, 'POST');
  assert.deepEqual(JSON.parse(calls[0].body), {id: 'banana-pancakes'});
  assert.equal(btn.getAttribute('aria-pressed'), 'true');
  assert.equal(btn.getAttribute('aria-label'), 'Remove Banana Pancakes from My Cookbook');
  assert.equal(btn.classList.contains('saved'), true);
  assert.match(btn.textContent, /Saved/);
  assert.match(btn.textContent, /✓/);
  assert.doesNotMatch(btn.textContent, /\+/);
  assert.equal(dom.buttons[0].getAttribute('aria-pressed'), 'false', 'other cards stay untouched');
});

test('removing a saved card DELETEs /api/cookbook/<id> and returns to the unsaved state', async () => {
  const dom = browseDom(['tomato-pasta']);
  const calls = await mount(dom.doc, () => ({ok: true, status: 200, body: {recipe_ids: []}}));
  const btn = dom.buttons[2];
  btn.click();
  await settle();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/cookbook/tomato-pasta');
  assert.equal(calls[0].method, 'DELETE');
  assert.equal(btn.getAttribute('aria-pressed'), 'false');
  assert.equal(btn.getAttribute('aria-label'), 'Save Tomato Basil Pasta to My Cookbook');
  assert.equal(btn.classList.contains('saved'), false);
  assert.match(btn.textContent, /Save/);
  assert.doesNotMatch(btn.textContent, /Saved|✓/);
  assert.match(btn.textContent, /\+/);
});

test('save then remove round-trips through POST and DELETE on the same button', async () => {
  const dom = browseDom();
  const calls = await mount(dom.doc);
  const btn = dom.buttons[0];
  btn.click();
  await settle();
  btn.click();
  await settle();
  assert.deepEqual(calls.map((c) => `${c.method} ${c.url}`), ['POST /api/cookbook', 'DELETE /api/cookbook/lentil-soup']);
  assert.equal(btn.getAttribute('aria-pressed'), 'false');
});

test('a failed HTTP response reverts the card and announces the error politely', async () => {
  const dom = browseDom();
  const calls = await mount(dom.doc, () => ({ok: false, status: 500, body: {error: 'boom'}}));
  const btn = dom.buttons[0];
  btn.click();
  await settle();
  assert.equal(calls.length, 1);
  assert.equal(btn.getAttribute('aria-pressed'), 'false');
  assert.equal(btn.classList.contains('saved'), false);
  assert.equal(btn.getAttribute('aria-label'), 'Save Red Lentil Soup to My Cookbook');
  assert.doesNotMatch(btn.textContent, /Saved|✓/);
  assert.ok(statusText(dom.doc).includes(ERROR), `expected "${ERROR}" in a polite status region, got: ${statusText(dom.doc)}`);
});

test('a network failure when removing reverts to saved and announces the error', async () => {
  const dom = browseDom(['banana-pancakes']);
  await mount(dom.doc, () => new TypeError('network down'));
  const btn = dom.buttons[1];
  btn.click();
  await settle();
  assert.equal(btn.getAttribute('aria-pressed'), 'true');
  assert.equal(btn.classList.contains('saved'), true);
  assert.equal(btn.getAttribute('aria-label'), 'Remove Banana Pancakes from My Cookbook');
  assert.match(btn.textContent, /Saved/);
  assert.ok(statusText(dom.doc).includes(ERROR));
});

test('no error is announced after a successful toggle', async () => {
  const dom = browseDom();
  const calls = await mount(dom.doc);
  dom.buttons[0].click();
  await settle();
  assert.equal(calls.length, 1, 'the toggle must reach /api/cookbook');
  assert.ok(!statusText(dom.doc).includes(ERROR));
});

// ---------- detail page uses the same path ----------
test('the detail-page [data-action=cookbook] button saves and removes through /api/cookbook', async () => {
  const {doc, btn} = detailDom(false);
  const calls = await mount(doc);
  btn.click();
  await settle();
  assert.equal(calls[0].url, '/api/cookbook');
  assert.equal(calls[0].method, 'POST');
  assert.deepEqual(JSON.parse(calls[0].body), {id: 'lentil-soup'});
  assert.equal(btn.getAttribute('aria-pressed'), 'true');
  assert.equal(btn.getAttribute('aria-label'), 'Remove Red Lentil Soup from My Cookbook');
  assert.equal(btn.classList.contains('saved'), true);
  assert.match(btn.textContent, /Saved/);
  btn.click();
  await settle();
  assert.equal(calls[1].method, 'DELETE');
  assert.equal(calls[1].url, '/api/cookbook/lentil-soup');
  assert.equal(btn.getAttribute('aria-pressed'), 'false');
});

test('a failed detail-page toggle reverts and announces the error', async () => {
  const {doc, btn} = detailDom(true);
  const calls = await mount(doc, () => ({ok: false, status: 503, body: {}}));
  btn.click();
  await settle();
  assert.equal(calls.length, 1);
  assert.equal(btn.getAttribute('aria-pressed'), 'true');
  assert.equal(btn.classList.contains('saved'), true);
  assert.ok(statusText(doc).includes(ERROR));
});

test('only /api/cookbook endpoints are ever called', async () => {
  const dom = browseDom();
  const calls = await mount(dom.doc);
  type(dom, 'basil');
  dom.buttons.forEach((b) => b.click());
  await settle();
  dom.buttons.forEach((b) => b.click());
  await settle();
  assert.equal(calls.length, 6);
  for (const c of calls) assert.match(c.url, /^\/api\/cookbook(\/[a-z0-9-]+)?$/);
});

// ---------- static source guarantees ----------
test('app.js has no legacy endpoint, film-domain or watchlist symbol and no network image', () => {
  const src = readFileSync(APP_URL, 'utf8');
  const banned = ['pocket', 'movie', 'movies', 'film', 'films', 'cinema', 'watchlist', 'poster', 'posters', 'runtime', 'rating', 'ratings', 'genre', 'genres'];
  const words = src.toLowerCase().split(/[^a-z]+/);
  for (const term of banned) assert.ok(!words.includes(term), `app.js still mentions "${term}"`);
  assert.doesNotMatch(src, /matchesMovie|nextWatchlist|\.movie-card|dataset\.title/);
  assert.doesNotMatch(src, /\/api\/(movies|watchlist)|\/movie\b/);
  assert.doesNotMatch(src, /https?:\/\/|new Image\(|\.(png|jpe?g|gif|webp|svg)\b/i);
  assert.match(src, /\/api\/cookbook/);
});
