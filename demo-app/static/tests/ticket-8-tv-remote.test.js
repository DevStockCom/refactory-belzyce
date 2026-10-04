// Acceptance tests for ticket #8: TV remote handling in tv-browse.js and tv-detail.js.
// A tiny in-memory DOM is installed on globalThis before each script is imported, so no browser is needed.
import test, {before} from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';

const STATIC = new URL('../', import.meta.url);
const BROWSE_URL = new URL('../tv-browse.js', import.meta.url);
const DETAIL_URL = new URL('../tv-detail.js', import.meta.url);
const APP_URL = new URL('../app.js', import.meta.url);

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
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  set textContent(v) {
    this.children.forEach((c) => { c.parentNode = null; });
    this.children = [];
    this._text = String(v);
  }
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
  append(...cs) { cs.forEach((c) => this.appendChild(c)); }
  focus() {}
  blur() {}
  scrollIntoView() {}
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
        if (node._matchOne?.(chain[chain.length - 1])) chain.pop();
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

// ---------- recording harness ----------
const original = {document: globalThis.document, fetch: globalThis.fetch, window: globalThis.window, location: globalThis.location};
let fetchCalls = [];
let loadCount = 0;

// One stable fetch for the whole file: app.js is evaluated once per process and keeps the fetch it saw first.
globalThis.fetch = async (url, init = {}) => {
  fetchCalls.push({url: String(url), method: (init.method || 'GET').toUpperCase(), body: init.body});
  return {ok: true, status: 200, json: async () => ({recipe_ids: []}), text: async () => '{}'};
};

function instrument(doc, log) {
  for (const el of doc.all()) {
    el.focus = (opts) => { doc.activeElement = el; log.push({type: 'focus', el, opts}); };
    el.scrollIntoView = (opts) => { log.push({type: 'scroll', el, opts}); };
  }
}

function install(doc) {
  const nav = [];
  const winListeners = {};
  const location = {
    href: 'http://localhost/',
    assign: (u) => nav.push(String(u)),
    replace: (u) => nav.push(String(u)),
  };
  Object.defineProperty(location, 'href', {get: () => 'http://localhost/', set: (u) => nav.push(String(u)), configurable: true});
  globalThis.document = doc;
  globalThis.location = location;
  globalThis.window = {
    document: doc,
    location,
    addEventListener: (t, fn) => { (winListeners[t] ||= []).push(fn); },
    removeEventListener() {},
  };
  return {nav, winListeners};
}

async function load(url, doc, log) {
  assert.ok(existsSync(url), `${url.pathname.split('/').pop()} has not been added to demo-app/static yet`);
  instrument(doc, log);
  const env = install(doc);
  try {
    await import(`${url.href}?run=${++loadCount}`);
  } catch (error) {
    assert.fail(`${url.pathname.split('/').pop()} must load and bind the TV page: ${error.message}`);
  }
  await settle();
  return env;
}

async function settle() {
  for (let i = 0; i < 6; i += 1) await new Promise((r) => setTimeout(r, 0));
}

test.afterEach(() => {
  fetchCalls = [];
  globalThis.document = original.document;
  globalThis.window = original.window;
  globalThis.location = original.location;
});

// Sends a key to the focused element (bubbles to document) and then to window listeners; returns defaultPrevented.
function press(doc, env, key) {
  const ev = {type: 'keydown', key, bubbles: true};
  (doc.activeElement || doc.body).dispatchEvent(ev);
  if (!ev.stopped) for (const fn of env.winListeners.keydown || []) fn(ev);
  return Boolean(ev.defaultPrevented);
}

// ---------- TV browse fixtures ----------
const RAILS = [
  ['Popular this week', ['lentil-soup', 'banana-pancakes', 'tomato-pasta']],
  ['Ready in 30 minutes', ['tomato-pasta', 'banana-pancakes']],
  ['Vegetarian favourites', ['banana-pancakes', 'tomato-pasta', 'lentil-soup']],
  ['My Cookbook', []],
];

function browseDom(rails = RAILS) {
  const doc = makeDocument();
  doc.body.setAttribute('data-mode', 'tv');
  for (const [name, ids] of rails) {
    const cards = ids.map((id) => h(doc, 'article', {class: 'recipe-card', 'data-recipe-id': id, 'data-search': id}, [
      h(doc, 'a', {href: `/recipe/${id}?mode=tv`, 'aria-label': `View ${id}`}, [], id),
      h(doc, 'button', {type: 'button', class: 'cookbook-toggle', 'data-recipe-id': id, 'aria-pressed': 'false'}, [], 'Save'),
    ]));
    const track = h(doc, 'div', {class: 'rail-track'}, cards);
    if (!ids.length) track.appendChild(h(doc, 'p', {class: 'empty'}, [], 'Your cookbook is empty. Save a recipe to see it here.'));
    doc.body.appendChild(h(doc, 'section', {class: 'tv-rail', 'data-rail': name}, [h(doc, 'h2', {}, [], name), track]));
  }
  const grid = doc.querySelectorAll('.tv-rail').map((rail) => rail.querySelectorAll('.recipe-card'));
  return {doc, grid};
}

const cardOf = (doc) => doc.activeElement?.closest?.('.recipe-card') ?? null;

function where(dom) {
  const card = cardOf(dom.doc);
  if (!card) return null;
  for (let r = 0; r < dom.grid.length; r += 1) {
    const i = dom.grid[r].indexOf(card);
    if (i >= 0) return {rail: r, index: i};
  }
  return null;
}

async function mountBrowse(rails) {
  const dom = browseDom(rails);
  const log = [];
  const env = await load(BROWSE_URL, dom.doc, log);
  return {...dom, log, env};
}

function assertRevealed(log, el, message) {
  const focusAt = log.map((e, i) => (e.type === 'focus' && e.el === el ? i : -1)).filter((i) => i >= 0).pop();
  assert.notEqual(focusAt, undefined, `${message}: element was never focused`);
  assert.deepEqual(log[focusAt].opts, {preventScroll: true}, `${message}: focus must use preventScroll`);
  const scroll = log.slice(focusAt + 1).find((e) => e.type === 'scroll' && e.el === el);
  assert.ok(scroll, `${message}: scrollIntoView must be called after focus`);
  assert.deepEqual(scroll.opts, {block: 'nearest', inline: 'nearest'}, `${message}: scroll options`);
}

// ---------- TV browse ----------
test('on load the first card of the first rail is focused and scrolled into view', async () => {
  const dom = await mountBrowse();
  assert.deepEqual(where(dom), {rail: 0, index: 0});
  assertRevealed(dom.log, dom.doc.activeElement, 'first card');
});

test('ArrowRight and ArrowLeft move within a rail, clamp at the ends and prevent default', async () => {
  const dom = await mountBrowse();
  assert.equal(press(dom.doc, dom.env, 'ArrowRight'), true);
  assert.deepEqual(where(dom), {rail: 0, index: 1});
  press(dom.doc, dom.env, 'ArrowRight');
  assert.deepEqual(where(dom), {rail: 0, index: 2});
  press(dom.doc, dom.env, 'ArrowRight');
  assert.deepEqual(where(dom), {rail: 0, index: 2}, 'stays on the last card');
  assert.equal(press(dom.doc, dom.env, 'ArrowLeft'), true);
  assert.deepEqual(where(dom), {rail: 0, index: 1});
  press(dom.doc, dom.env, 'ArrowLeft');
  press(dom.doc, dom.env, 'ArrowLeft');
  assert.deepEqual(where(dom), {rail: 0, index: 0}, 'stays on the first card');
});

test('ArrowDown and ArrowUp move across rails choosing the nearest card index and skip the empty rail', async () => {
  const dom = await mountBrowse();
  press(dom.doc, dom.env, 'ArrowRight');
  press(dom.doc, dom.env, 'ArrowRight');
  assert.equal(press(dom.doc, dom.env, 'ArrowDown'), true);
  assert.deepEqual(where(dom), {rail: 1, index: 1}, 'index clamps to the shorter rail');
  press(dom.doc, dom.env, 'ArrowDown');
  assert.deepEqual(where(dom), {rail: 2, index: 1});
  press(dom.doc, dom.env, 'ArrowDown');
  assert.deepEqual(where(dom), {rail: 2, index: 1}, 'empty My Cookbook rail is skipped; stays put at the bottom');
  assert.equal(press(dom.doc, dom.env, 'ArrowUp'), true);
  assert.deepEqual(where(dom), {rail: 1, index: 1});
  press(dom.doc, dom.env, 'ArrowUp');
  press(dom.doc, dom.env, 'ArrowUp');
  assert.deepEqual(where(dom), {rail: 0, index: 1}, 'stays on the top rail');
});

test('every focus move scrolls the newly focused card into view', async () => {
  const dom = await mountBrowse();
  for (const key of ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp']) {
    press(dom.doc, dom.env, key);
    assertRevealed(dom.log, dom.doc.activeElement, key);
  }
});

test('a populated My Cookbook rail is reachable with ArrowDown', async () => {
  const rails = RAILS.map(([n, ids]) => [n, n === 'My Cookbook' ? ['lentil-soup', 'tomato-pasta'] : ids]);
  const dom = await mountBrowse(rails);
  for (let i = 0; i < 3; i += 1) press(dom.doc, dom.env, 'ArrowDown');
  assert.deepEqual(where(dom), {rail: 3, index: 0});
});

test('Enter on a card navigates to /recipe/<id>?mode=tv and prevents default', async () => {
  const dom = await mountBrowse();
  press(dom.doc, dom.env, 'ArrowRight');
  const prevented = press(dom.doc, dom.env, 'Enter');
  assert.equal(prevented, true);
  assert.deepEqual(dom.env.nav, ['/recipe/banana-pancakes?mode=tv']);
});

test('Enter after moving to another rail opens that card', async () => {
  const dom = await mountBrowse();
  press(dom.doc, dom.env, 'ArrowDown');
  press(dom.doc, dom.env, 'ArrowRight');
  press(dom.doc, dom.env, 'Enter');
  assert.deepEqual(dom.env.nav, ['/recipe/banana-pancakes?mode=tv']);
});

test('position is tracked from document.activeElement, so externally focused cards are respected', async () => {
  const dom = await mountBrowse();
  dom.doc.activeElement = dom.grid[2][0];
  press(dom.doc, dom.env, 'ArrowRight');
  assert.deepEqual(where(dom), {rail: 2, index: 1});
  dom.doc.activeElement = dom.grid[1][1];
  press(dom.doc, dom.env, 'ArrowUp');
  assert.deepEqual(where(dom), {rail: 0, index: 1});
});

test('unhandled keys are left alone: no preventDefault, no focus change, no navigation', async () => {
  const dom = await mountBrowse();
  const before = dom.doc.activeElement;
  for (const key of ['Tab', 'a', 'Escape', 'Backspace', ' ', 'Shift', 'F5']) {
    assert.equal(press(dom.doc, dom.env, key), false, `${key} must not be prevented`);
  }
  assert.equal(dom.doc.activeElement, before);
  assert.deepEqual(dom.env.nav, []);
});

test('tv-browse is a no-op when the rail hooks are absent', async () => {
  const doc = makeDocument();
  doc.body.appendChild(h(doc, 'p', {}, [], 'nothing here'));
  const log = [];
  const env = await load(BROWSE_URL, doc, log);
  for (const key of ['ArrowDown', 'ArrowLeft', 'Enter', 'Escape']) {
    assert.equal(press(doc, env, key), false);
  }
  assert.deepEqual(log, []);
  assert.deepEqual(env.nav, []);
});

test('tv-browse does not throw or steal keys when every rail is empty', async () => {
  const dom = await mountBrowse([['My Cookbook', []]]);
  assert.equal(press(dom.doc, dom.env, 'ArrowDown'), false);
  assert.equal(press(dom.doc, dom.env, 'Enter'), false);
  assert.deepEqual(dom.env.nav, []);
});

// ---------- TV detail ----------
const RECIPE = {id: 'lentil-soup', title: 'Red Lentil Soup'};

function detailDom() {
  const doc = makeDocument();
  doc.body.setAttribute('data-mode', 'tv');
  const back = h(doc, 'a', {class: 'back', 'data-action': 'back', href: '/?mode=tv'}, [], '← Back to recipes');
  const btn = h(doc, 'button', {
    type: 'button',
    class: 'cookbook-toggle',
    'data-action': 'cookbook',
    'data-recipe-id': RECIPE.id,
    'data-recipe-title': RECIPE.title,
    'aria-pressed': 'false',
    'aria-label': `Save ${RECIPE.title} to My Cookbook`,
  }, [
    h(doc, 'span', {class: 'toggle-icon', 'aria-hidden': 'true'}, [], '+'),
    h(doc, 'span', {class: 'toggle-text'}, [], 'Save'),
  ]);
  doc.body.appendChild(back);
  doc.body.appendChild(btn);
  return {doc, back, btn};
}

// app.js binds to the first document it sees and is cached for the process, so every detail test reuses one document.
const shared = detailDom();

async function mountDetail() {
  const {doc, back, btn} = shared;
  doc.listeners = {};
  btn.setAttribute('aria-pressed', 'false');
  btn.setAttribute('aria-label', `Save ${RECIPE.title} to My Cookbook`);
  btn.classList.remove('saved');
  btn.querySelector('.toggle-icon').textContent = '+';
  btn.querySelector('.toggle-text').textContent = 'Save';
  doc.activeElement = doc.body;
  const log = [];
  back.listeners = {};
  const clicks = [];
  back.addEventListener('click', () => clicks.push('back'));
  const env = await load(DETAIL_URL, doc, log);
  return {doc, back, btn, log, env, clicks};
}

before(async () => {
  instrument(shared.doc, []);
  install(shared.doc);
  await import(APP_URL.href);
  await settle();
});

test('on load the back action is focused and scrolled into view', async () => {
  const dom = await mountDetail();
  assert.equal(dom.doc.activeElement, dom.back);
  assertRevealed(dom.log, dom.back, 'back action');
});

test('ArrowDown reaches My Cookbook, ArrowUp returns to back, and the ends clamp', async () => {
  const dom = await mountDetail();
  assert.equal(press(dom.doc, dom.env, 'ArrowUp'), true);
  assert.equal(dom.doc.activeElement, dom.back, 'ArrowUp on the first action stays put');
  assert.equal(press(dom.doc, dom.env, 'ArrowDown'), true);
  assert.equal(dom.doc.activeElement, dom.btn);
  assertRevealed(dom.log, dom.btn, 'cookbook action');
  press(dom.doc, dom.env, 'ArrowDown');
  assert.equal(dom.doc.activeElement, dom.btn, 'ArrowDown on the last action stays put');
  press(dom.doc, dom.env, 'ArrowUp');
  assert.equal(dom.doc.activeElement, dom.back);
});

test('Enter on My Cookbook saves the recipe through the shared cookbook handler', async () => {
  const dom = await mountDetail();
  press(dom.doc, dom.env, 'ArrowDown');
  const prevented = press(dom.doc, dom.env, 'Enter');
  await settle();
  assert.equal(prevented, true);
  const posts = fetchCalls.filter((c) => c.method === 'POST');
  assert.equal(posts.length, 1, 'exactly one save request');
  assert.equal(posts[0].url, '/api/cookbook');
  assert.deepEqual(JSON.parse(posts[0].body), {id: RECIPE.id});
  assert.equal(dom.btn.getAttribute('aria-pressed'), 'true');
  assert.equal(dom.btn.getAttribute('aria-label'), `Remove ${RECIPE.title} from My Cookbook`);
  assert.deepEqual(dom.clicks, [], 'back must not be activated');
});

test('Enter on My Cookbook again removes the recipe', async () => {
  const dom = await mountDetail();
  press(dom.doc, dom.env, 'ArrowDown');
  press(dom.doc, dom.env, 'Enter');
  await settle();
  press(dom.doc, dom.env, 'Enter');
  await settle();
  const deletes = fetchCalls.filter((c) => c.method === 'DELETE');
  assert.equal(deletes.length, 1);
  assert.equal(deletes[0].url, `/api/cookbook/${RECIPE.id}`);
  assert.equal(dom.btn.getAttribute('aria-pressed'), 'false');
});

test('Enter on back clicks the back link and does not touch the cookbook', async () => {
  const dom = await mountDetail();
  press(dom.doc, dom.env, 'Enter');
  await settle();
  assert.deepEqual(dom.clicks, ['back']);
  assert.deepEqual(fetchCalls, []);
});

test('Escape and Backspace navigate to /?mode=tv and prevent default', async () => {
  for (const key of ['Escape', 'Backspace']) {
    const dom = await mountDetail();
    assert.equal(press(dom.doc, dom.env, key), true, `${key} prevented`);
    assert.deepEqual(dom.env.nav, ['/?mode=tv'], `${key} destination`);
  }
});

test('unhandled keys on TV detail are not prevented and cause no navigation', async () => {
  const dom = await mountDetail();
  for (const key of ['Tab', 'a', 'ArrowLeft', 'ArrowRight', ' ', 'Shift']) {
    assert.equal(press(dom.doc, dom.env, key), false, `${key} must not be prevented`);
  }
  assert.equal(dom.doc.activeElement, dom.back);
  assert.deepEqual(dom.env.nav, []);
  assert.deepEqual(fetchCalls, []);
});

test('tv-detail is a no-op when the action hooks are absent', async () => {
  const doc = makeDocument();
  doc.body.appendChild(h(doc, 'p', {}, [], 'nothing here'));
  const log = [];
  const env = await load(DETAIL_URL, doc, log);
  for (const key of ['ArrowDown', 'Enter', 'Escape', 'Backspace']) {
    assert.equal(press(doc, env, key), false);
  }
  assert.deepEqual(log, []);
  assert.deepEqual(env.nav, []);
});

// ---------- source-level constraints ----------
const read = (name) => {
  const url = new URL(name, STATIC);
  assert.ok(existsSync(url), `${name} has not been added to demo-app/static yet`);
  return readFileSync(url, 'utf8');
};
const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

test('both scripts exist and reuse tv-nav.js instead of duplicating its logic', () => {
  const browse = stripComments(read('tv-browse.js'));
  const detail = stripComments(read('tv-detail.js'));
  assert.match(browse, /import\s*\{[^}]*\bnextFocus\b[^}]*\}\s*from\s*['"]\.\/tv-nav\.js['"]/);
  assert.match(browse, /import\s*\{[^}]*\benterTarget\b[^}]*\}\s*from\s*['"]\.\/tv-nav\.js['"]/);
  assert.match(detail, /import\s*\{[^}]*\bdetailNext\b[^}]*\}\s*from\s*['"]\.\/tv-nav\.js['"]/);
  assert.match(detail, /import\s*\{[^}]*\bdetailExit\b[^}]*\}\s*from\s*['"]\.\/tv-nav\.js['"]/);
  assert.match(detail, /from\s*['"]\.\/app\.js['"]/, 'tv-detail reuses the cookbook handler from app.js');
  for (const [name, src] of [['tv-browse.js', browse], ['tv-detail.js', detail]]) {
    assert.doesNotMatch(src, /\/recipe\//, `${name} must not rebuild destinations`);
    assert.doesNotMatch(src, /mode=tv/, `${name} must not rebuild destinations`);
    assert.doesNotMatch(src, /\/api\/cookbook/, `${name} must not re-implement cookbook calls`);
  }
  assert.match(browse + detail, /preventScroll:\s*true/);
  assert.match(browse + detail, /block:\s*['"]nearest['"]/);
  assert.match(browse + detail, /inline:\s*['"]nearest['"]/);
});

test('the TV scripts contain no banned terminology', () => {
  const terms = [['mo', 'vie'], ['fi', 'lm'], ['cin', 'ema'], ['watch', 'list'], ['pos', 'ter'], ['run', 'time'], ['rat', 'ing'], ['gen', 're']].map((p) => p.join(''));
  const wordRe = new RegExp(`\\b(${terms.join('|')})s?\\b`, 'i');
  for (const name of ['tv-browse.js', 'tv-detail.js']) {
    const src = read(name);
    assert.doesNotMatch(src, wordRe, `${name} banned term`);
    assert.doesNotMatch(src, /\bPC\b/, `${name} standalone PC`);
  }
});
