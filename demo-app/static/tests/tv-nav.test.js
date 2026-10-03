import test from 'node:test';
import assert from 'node:assert/strict';
import {nextFocus, enterTarget, detailNext, DETAIL_ACTIONS, detailExit, TV_HOME_URL} from '../tv-nav.js';

test('nextFocus moves within a rail and clamps', () => {
  assert.deepEqual(nextFocus([3], {rail: 0, index: 0}, 'ArrowRight'), {rail: 0, index: 1});
  assert.deepEqual(nextFocus([3], {rail: 0, index: 2}, 'ArrowRight'), {rail: 0, index: 2});
  assert.deepEqual(nextFocus([3], {rail: 0, index: 0}, 'ArrowLeft'), {rail: 0, index: 0});
});

test('nextFocus moves across rails with nearest index, skipping empty rails', () => {
  assert.deepEqual(nextFocus([5, 2], {rail: 0, index: 4}, 'ArrowDown'), {rail: 1, index: 1});
  assert.deepEqual(nextFocus([3, 0, 2], {rail: 0, index: 2}, 'ArrowDown'), {rail: 2, index: 1});
  assert.deepEqual(nextFocus([3, 0, 2], {rail: 2, index: 0}, 'ArrowUp'), {rail: 0, index: 0});
  assert.deepEqual(nextFocus([3, 2], {rail: 1, index: 1}, 'ArrowDown'), {rail: 1, index: 1});
});

test('nextFocus handles empty shapes and unhandled keys', () => {
  const start = {rail: 0, index: 0};
  assert.deepEqual(nextFocus([], start, 'ArrowDown'), start);
  assert.deepEqual(nextFocus([0, 0], start, 'ArrowRight'), start);
  assert.equal(nextFocus([2], start, 'Enter'), null);
});

test('nextFocus tolerates a missing position', () => {
  assert.deepEqual(nextFocus([3], undefined, 'ArrowRight'), {rail: 0, index: 1});
  assert.deepEqual(nextFocus([], null, 'ArrowDown'), {rail: 0, index: 0});
  assert.equal(nextFocus([3], null, 'Enter'), null);
});

test('enterTarget keeps TV mode', () => {
  assert.equal(enterTarget('a b'), '/recipe/a%20b?mode=tv');
});

test('detail navigation and exit', () => {
  assert.equal(detailNext(DETAIL_ACTIONS, 'back', 'ArrowDown'), 'cookbook');
  assert.equal(detailNext(DETAIL_ACTIONS, 'cookbook', 'ArrowDown'), 'cookbook');
  assert.equal(detailNext(DETAIL_ACTIONS, 'back', 'ArrowUp'), 'back');
  assert.equal(detailNext(DETAIL_ACTIONS, 'back', 'Enter'), null);
  assert.equal(detailNext([], 'back', 'ArrowDown'), null);
  assert.equal(detailExit('Escape'), TV_HOME_URL);
  assert.equal(detailExit('Backspace'), '/?mode=tv');
  assert.equal(detailExit('Enter'), null);
});
