import test from 'node:test';
import assert from 'node:assert/strict';
import * as logic from '../app-logic.js';

const loadNav = () => import('../tv-nav.js');
const BANNED = /\b(pocket cinema|pc|movies?|films?|cinema|watchlist|posters?|runtime|ratings?|genres?)\b|matchesMovie|nextWatchlist/i;

test('app-logic exports the recipe API and drops the film-named exports', () => {
  for (const name of ['matchesRecipe', 'formatResultCount', 'EMPTY_MESSAGE', 'toggleSavedIds', 'cookbookToggleView']) {
    assert.ok(name in logic, `missing export ${name}`);
  }
  assert.equal('matchesMovie' in logic, false);
  assert.equal('nextWatchlist' in logic, false);
  for (const name of Object.keys(logic)) assert.doesNotMatch(name, BANNED);
});

test('matchesRecipe handles case, whitespace and empty query', () => {
  const text = 'lemon pancakes breakfast vegetarian flour eggs';
  assert.equal(logic.matchesRecipe(text, 'LEMON'), true);
  assert.equal(logic.matchesRecipe(text, '  Eggs \t'), true);
  assert.equal(logic.matchesRecipe(text, 'salmon'), false);
  assert.equal(logic.matchesRecipe(text, ''), true);
  assert.equal(logic.matchesRecipe(text, '   '), true);
  assert.equal(logic.matchesRecipe('', ''), true);
  assert.equal(logic.matchesRecipe('', 'x'), false);
});

test('formatResultCount and EMPTY_MESSAGE', () => {
  assert.equal(logic.formatResultCount(1), '1 recipe');
  assert.equal(logic.formatResultCount(2), '2 recipes');
  assert.equal(logic.formatResultCount(12), '12 recipes');
  assert.equal(logic.formatResultCount(0), '0 recipes');
  assert.equal(logic.EMPTY_MESSAGE, 'No recipes found. Try another ingredient or dish.');
});

test('toggleSavedIds adds, removes, sorts and does not mutate', () => {
  const input = ['b', 'd'];
  assert.deepEqual(logic.toggleSavedIds(input, 'c'), ['b', 'c', 'd']);
  assert.deepEqual(input, ['b', 'd']);
  assert.deepEqual(logic.toggleSavedIds(['a', 'b'], 'a'), ['b']);
  assert.deepEqual(logic.toggleSavedIds([], 'a'), ['a']);
  assert.deepEqual(logic.toggleSavedIds(['a'], 'a'), []);
});

test('cookbookToggleView derives saved and unsaved views', () => {
  assert.deepEqual(logic.cookbookToggleView('Lemon Pancakes', true), {
    text: 'Saved', icon: '✓', label: 'Remove Lemon Pancakes from My Cookbook', pressed: true,
  });
  assert.deepEqual(logic.cookbookToggleView('Lemon Pancakes', false), {
    text: 'Save', icon: '+', label: 'Save Lemon Pancakes to My Cookbook', pressed: false,
  });
});

test('tv-nav exports the expected API without film-named symbols', async () => {
  const nav = await loadNav();
  for (const name of ['nextFocus', 'enterTarget', 'detailNext', 'DETAIL_ACTIONS', 'detailExit', 'TV_HOME_URL']) {
    assert.ok(name in nav, `missing export ${name}`);
  }
  for (const name of Object.keys(nav)) assert.doesNotMatch(name, BANNED);
  assert.deepEqual([...nav.DETAIL_ACTIONS], ['back', 'cookbook']);
  assert.equal(nav.TV_HOME_URL, '/?mode=tv');
});

test('nextFocus moves left and right within a rail and clamps at edges', async () => {
  const {nextFocus} = await loadNav();
  const shape = [3, 2];
  assert.deepEqual(nextFocus(shape, {rail: 0, index: 0}, 'ArrowRight'), {rail: 0, index: 1});
  assert.deepEqual(nextFocus(shape, {rail: 0, index: 1}, 'ArrowLeft'), {rail: 0, index: 0});
  assert.deepEqual(nextFocus(shape, {rail: 0, index: 2}, 'ArrowRight'), {rail: 0, index: 2});
  assert.deepEqual(nextFocus(shape, {rail: 0, index: 0}, 'ArrowLeft'), {rail: 0, index: 0});
});

test('nextFocus moves up and down with nearest index and clamps at rail edges', async () => {
  const {nextFocus} = await loadNav();
  const shape = [5, 2, 4];
  assert.deepEqual(nextFocus(shape, {rail: 0, index: 4}, 'ArrowDown'), {rail: 1, index: 1});
  assert.deepEqual(nextFocus(shape, {rail: 1, index: 1}, 'ArrowDown'), {rail: 2, index: 1});
  assert.deepEqual(nextFocus(shape, {rail: 2, index: 3}, 'ArrowUp'), {rail: 1, index: 1});
  assert.deepEqual(nextFocus(shape, {rail: 0, index: 2}, 'ArrowUp'), {rail: 0, index: 2});
  assert.deepEqual(nextFocus(shape, {rail: 2, index: 2}, 'ArrowDown'), {rail: 2, index: 2});
});

test('nextFocus skips empty rails', async () => {
  const {nextFocus} = await loadNav();
  const shape = [3, 0, 0, 2];
  assert.deepEqual(nextFocus(shape, {rail: 0, index: 2}, 'ArrowDown'), {rail: 3, index: 1});
  assert.deepEqual(nextFocus(shape, {rail: 3, index: 0}, 'ArrowUp'), {rail: 0, index: 0});
  assert.deepEqual(nextFocus([2, 0], {rail: 0, index: 1}, 'ArrowDown'), {rail: 0, index: 1});
  assert.deepEqual(nextFocus([0, 2], {rail: 1, index: 0}, 'ArrowUp'), {rail: 1, index: 0});
});

test('nextFocus returns null for unhandled keys and never throws on empty input', async () => {
  const {nextFocus} = await loadNav();
  assert.equal(nextFocus([3], {rail: 0, index: 0}, 'Enter'), null);
  assert.equal(nextFocus([3], {rail: 0, index: 0}, 'a'), null);
  assert.equal(nextFocus([3], {rail: 0, index: 0}, ''), null);
  const start = {rail: 0, index: 0};
  for (const key of ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown']) {
    assert.deepEqual(nextFocus([], start, key), start);
    assert.deepEqual(nextFocus([0, 0], start, key), start);
  }
  assert.equal(nextFocus([], start, 'Enter'), null);
});

test('enterTarget keeps TV mode and encodes the id', async () => {
  const {enterTarget} = await loadNav();
  assert.equal(enterTarget('lemon-pancakes'), '/recipe/lemon-pancakes?mode=tv');
  assert.equal(enterTarget('a b/c'), '/recipe/a%20b%2Fc?mode=tv');
});

test('detailNext moves between back and cookbook with clamping', async () => {
  const {detailNext, DETAIL_ACTIONS} = await loadNav();
  assert.equal(detailNext(DETAIL_ACTIONS, 'back', 'ArrowDown'), 'cookbook');
  assert.equal(detailNext(DETAIL_ACTIONS, 'cookbook', 'ArrowUp'), 'back');
  assert.equal(detailNext(DETAIL_ACTIONS, 'back', 'ArrowUp'), 'back');
  assert.equal(detailNext(DETAIL_ACTIONS, 'cookbook', 'ArrowDown'), 'cookbook');
  assert.equal(detailNext(DETAIL_ACTIONS, 'back', 'Enter'), null);
  assert.equal(detailNext(DETAIL_ACTIONS, 'back', 'ArrowLeft'), null);
});

test('detailNext tolerates unknown current action and empty list', async () => {
  const {detailNext, DETAIL_ACTIONS} = await loadNav();
  assert.equal(detailNext(DETAIL_ACTIONS, 'bogus', 'ArrowDown'), 'back');
  assert.doesNotThrow(() => detailNext([], 'back', 'ArrowDown'));
});

test('detailExit returns the TV home URL for Escape and Backspace only', async () => {
  const {detailExit} = await loadNav();
  assert.equal(detailExit('Escape'), '/?mode=tv');
  assert.equal(detailExit('Backspace'), '/?mode=tv');
  assert.equal(detailExit('Enter'), null);
  assert.equal(detailExit('ArrowUp'), null);
  assert.equal(detailExit(''), null);
});
