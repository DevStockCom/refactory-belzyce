import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';

const raw = JSON.parse(readFileSync('demo-app/recipes.json', 'utf8'));
const rs = Array.isArray(raw) ? raw : raw.recipes;
const text = (r) => [r.title, r.description, r.category, ...r.dietary_tags, ...r.ingredients].join(' ').toLowerCase();

if (process.argv.length < 3) {
  for (const r of rs) console.log(r.id, r.category, JSON.stringify(r.dietary_tags), JSON.stringify(r.ingredients.slice(0, 5)));
  console.log('non-ascii:', rs.some((r) => /[^\x00-\x7f]/.test(text(r))));
} else {
  const queries = JSON.parse(readFileSync(process.argv[2], 'utf8'));
  const texts = Object.fromEntries(rs.map((r) => [r.id, text(r)]));
  const cases = queries.map(([name, query]) => {
    const needle = query.trim().toLowerCase();
    return {name, query, ids: Object.keys(texts).filter((id) => texts[id].includes(needle))};
  });
  mkdirSync('demo-app/static/tests/fixtures', {recursive: true});
  writeFileSync('demo-app/static/tests/fixtures/search-parity.json', JSON.stringify({recipes: texts, cases}, null, 2) + '\n');
  for (const c of cases) console.log(c.name, JSON.stringify(c.query), c.ids.length);
}
