import test from 'node:test';
import assert from 'node:assert/strict';

globalThis.document = {querySelectorAll: () => []};
const {initTvBrowse} = await import('../tv-browse.js');

function fakeDom() {
  const link = {focus() { doc.activeElement = link; }, scrollIntoView() {}};
  const toggle = {focus() { doc.activeElement = toggle; }, scrollIntoView() {}};
  const card = {
    dataset: {recipeId: 'lentil-soup'},
    querySelector: () => link,
  };
  link.closest = () => card;
  toggle.closest = () => card;
  const listeners = [];
  const doc = {
    activeElement: null,
    querySelectorAll: (sel) => (sel === '.tv-rail[data-rail]' ? [{querySelectorAll: () => [card]}] : []),
    addEventListener: (type, fn) => listeners.push(fn),
  };
  const send = (key) => {
    const event = {key, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }};
    listeners.forEach((fn) => fn(event));
    return event.defaultPrevented;
  };
  return {doc, link, toggle, send};
}

test('Enter on a card link navigates; Enter on the save toggle inside the card is left native', () => {
  const nav = [];
  globalThis.location = {assign: (url) => nav.push(url)};
  const dom = fakeDom();
  initTvBrowse(dom.doc);
  assert.equal(dom.doc.activeElement, dom.link);
  assert.equal(dom.send('Enter'), true);
  assert.deepEqual(nav, ['/recipe/lentil-soup?mode=tv']);

  dom.toggle.focus();
  assert.equal(dom.send('Enter'), false, 'toggle keeps its native Enter activation');
  assert.deepEqual(nav, ['/recipe/lentil-soup?mode=tv']);
});
