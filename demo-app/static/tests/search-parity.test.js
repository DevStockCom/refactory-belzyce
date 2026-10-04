import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {matchesRecipe} from '../app-logic.js';

const data = JSON.parse(readFileSync(new URL('./fixtures/search-parity.json', import.meta.url), 'utf8'));

for (const c of data.cases) {
  test(`matchesRecipe over fixture texts: ${c.name}`, () => {
    const ids = data.recipes.filter((r) => matchesRecipe(r.search_text, c.query)).map((r) => r.id);
    assert.deepEqual(ids, c.expected_ids);
  });
}
