import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {matchesRecipe} from '../app-logic.js';

const fixturePath = new URL('./fixtures/search-parity.json', import.meta.url);

function load() {
  assert.ok(existsSync(fixturePath), 'missing parity fixture: static/tests/fixtures/search-parity.json');
  const data = JSON.parse(readFileSync(fixturePath, 'utf8'));
  const rawTexts = data.texts ?? data.recipes;
  assert.ok(rawTexts, 'fixture needs a per-recipe search_text collection');
  const texts = Array.isArray(rawTexts)
    ? rawTexts.map((r) => [r.id, r.search_text])
    : Object.entries(rawTexts);
  const rawCases = data.cases ?? data.queries;
  assert.ok(Array.isArray(rawCases) && rawCases.length, 'fixture needs query cases');
  const cases = rawCases.map((c) => [c.query, c.ids ?? c.expected_ids]);
  return {texts, cases};
}

test('matchesRecipe over fixture texts yields the fixture ids for every case', () => {
  const {texts, cases} = load();
  for (const [query, ids] of cases) {
    const got = texts.filter(([, text]) => matchesRecipe(text, query)).map(([id]) => id);
    assert.deepEqual(got, ids, `query ${JSON.stringify(query)}`);
  }
});

test('fixture includes mixed-case, padded, empty, no-match and hit queries', () => {
  const {texts, cases} = load();
  const queries = cases.map(([q]) => q);
  const byQuery = new Map(cases);
  assert.deepEqual(byQuery.get(''), texts.map(([id]) => id), 'empty query returns all');
  assert.ok(queries.some((q) => q.trim() && q !== q.toLowerCase()), 'mixed case');
  assert.ok(queries.some((q) => q.trim() && q !== q.trim()), 'padded whitespace');
  assert.ok(cases.some(([q, ids]) => q.trim() && ids.length === 0), 'no match');
  assert.ok(cases.some(([q, ids]) => q.trim() && ids.length > 0), 'at least one hit');
});

test('a matcher without trim/lowercase would be detected by the fixture', () => {
  const {texts, cases} = load();
  const drifted = cases.some(([q, ids]) => {
    const got = texts.filter(([, t]) => t.includes(q)).map(([id]) => id);
    return JSON.stringify(got) !== JSON.stringify(ids);
  });
  assert.ok(drifted);
});
