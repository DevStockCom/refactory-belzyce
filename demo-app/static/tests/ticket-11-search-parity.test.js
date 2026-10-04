import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {matchesRecipe} from '../app-logic.js';

const FIXTURE = new URL('./fixtures/search-parity.json', import.meta.url);

function load() {
  assert.ok(existsSync(FIXTURE), 'missing parity fixture search-parity.json');
  const data = JSON.parse(readFileSync(FIXTURE, 'utf8'));
  const texts = Array.isArray(data.recipes)
    ? Object.fromEntries(data.recipes.map((r) => [r.id, r.search_text]))
    : data.recipes;
  return {texts, cases: data.cases};
}

const idsOf = (c) => c.ids ?? c.expected_ids;

test('fixture has search text for recipes and a non-empty case list', () => {
  const {texts, cases} = load();
  assert.ok(Object.keys(texts).length >= 12);
  assert.ok(cases.length > 0);
});

test('matchesRecipe over fixture texts yields the fixture ids for every case', () => {
  const {texts, cases} = load();
  for (const c of cases) {
    const got = Object.keys(texts).filter((id) => matchesRecipe(texts[id], c.query));
    assert.deepEqual(got, idsOf(c), `case ${c.name ?? JSON.stringify(c.query)}`);
  }
});

test('fixture includes mixed-case, padded, empty, no-match and ingredient-style queries', () => {
  const {texts, cases} = load();
  const queries = cases.map((c) => c.query);
  assert.ok(queries.some((q) => q !== q.toLowerCase()), 'mixed-case');
  assert.ok(queries.some((q) => q.trim() && q !== q.trim()), 'padded whitespace');
  const empty = cases.find((c) => c.query === '');
  assert.ok(empty, 'empty query');
  assert.deepEqual(idsOf(empty), Object.keys(texts));
  assert.ok(cases.some((c) => c.query.trim() && idsOf(c).length === 0), 'no-match');
  assert.ok(cases.some((c) => idsOf(c).length > 0 && idsOf(c).length < Object.keys(texts).length), 'narrowing');
});

test('a drifted matcher would disagree with the fixture', () => {
  const {texts, cases} = load();
  const drifted = (text, q) => text.includes(q);
  const mismatch = cases.some((c) => {
    const got = Object.keys(texts).filter((id) => drifted(texts[id], c.query));
    return JSON.stringify(got) !== JSON.stringify(idsOf(c));
  });
  assert.ok(mismatch, 'case-sensitive/untrimmed matching must be caught by the fixture');
});
