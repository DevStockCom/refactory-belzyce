import test from 'node:test';
import assert from 'node:assert/strict';
import {matchesRecipe, formatResultCount, EMPTY_MESSAGE, toggleSavedIds, cookbookToggleView} from '../app-logic.js';

test('recipe matching ignores case and surrounding whitespace', () => {
  assert.equal(matchesRecipe('lemon pancakes breakfast vegetarian', '  VEGetarian '), true);
  assert.equal(matchesRecipe('lemon pancakes breakfast', 'salmon'), false);
  assert.equal(matchesRecipe('lemon pancakes', '  '), true);
  assert.equal(matchesRecipe('', ''), true);
});

test('result count and empty message', () => {
  assert.equal(formatResultCount(1), '1 recipe');
  assert.equal(formatResultCount(3), '3 recipes');
  assert.equal(EMPTY_MESSAGE, 'No recipes found. Try another ingredient or dish.');
});

test('saved ids toggle deterministically without mutation', () => {
  const input = ['b'];
  assert.deepEqual(toggleSavedIds(input, 'a'), ['a', 'b']);
  assert.deepEqual(input, ['b']);
  assert.deepEqual(toggleSavedIds(['a', 'b'], 'a'), ['b']);
});

test('cookbook toggle view reflects saved state', () => {
  assert.deepEqual(cookbookToggleView('Soup', true), {text: 'Saved', icon: '✓', label: 'Remove Soup from My Cookbook', pressed: true});
  assert.deepEqual(cookbookToggleView('Soup', false), {text: 'Save', icon: '+', label: 'Save Soup to My Cookbook', pressed: false});
});
