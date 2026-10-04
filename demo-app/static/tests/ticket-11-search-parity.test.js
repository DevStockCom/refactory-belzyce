// Ticket 11 acceptance: client matcher agrees with the shared parity fixture.
// Fixture: {recipes: [{id, search_text}], cases: [{name, query, expected_ids}]}
import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {matchesRecipe} from '../app-logic.js';

const FIXTURE = fileURLToPath(new URL('./fixtures/search-parity.json', import.meta.url));

function loadFixture() {
  assert.ok(existsSync(FIXTURE), `missing parity fixture: ${FIXTURE}`);
  const data = JSON.parse(readFileSync(FIXTURE, 'utf8'));
  assert.ok(Array.isArray(data.recipes) && data.recipes.length > 0, 'fixture needs recipes');
  assert.ok(Array.isArray(data.cases) && data.cases.length > 0, 'fixture needs cases');
  return data;
}

const idsFor = (data, query) =>
  data.recipes.filter((r) => matchesRecipe(r.search_text, query)).map((r) => r.id);

test('matchesRecipe over fixture texts yields the fixture ids for every case', () => {
  const data = loadFixture();
  for (const c of data.cases) {
    assert.deepEqual(idsFor(data, c.query), c.expected_ids, c.name);
  }
});

test('fixture includes mixed-case, padded, ingredient-only, empty and nonsense queries', () => {
  const data = loadFixture();
  const queries = data.cases.map((c) => c.query);
  assert.ok(queries.includes(''), 'empty query');
  assert.ok(queries.some((q) => q.trim() && q !== q.trim()), 'padded query');
  assert.ok(queries.some((q) => q.trim() && q.trim() !== q.trim().toLowerCase()), 'mixed-case query');
  assert.ok(data.cases.some((c) => c.query.trim() && c.expected_ids.length === 0), 'nonsense query');
  assert.deepEqual(data.cases.find((c) => c.query === '').expected_ids, data.recipes.map((r) => r.id));
  assert.ok(data.cases.some((c) => c.expected_ids.length > 0 && c.expected_ids.length < data.recipes.length),
    'strict-subset query');
});

test('padded and mixed-case queries agree with their normalised twins', () => {
  const data = loadFixture();
  for (const c of data.cases) {
    assert.deepEqual(c.expected_ids, idsFor(data, c.query.trim().toLowerCase()), c.name);
  }
});

test('a matcher without trim and lowercase would be caught by the fixture', () => {
  const data = loadFixture();
  const naive = (text, q) => text.includes(q);
  const broken = data.cases.filter((c) => {
    const got = data.recipes.filter((r) => naive(r.search_text, c.query)).map((r) => r.id);
    return JSON.stringify(got) !== JSON.stringify(c.expected_ids);
  });
  assert.ok(broken.length > 0, 'fixture must expose a drifted matcher');
});
