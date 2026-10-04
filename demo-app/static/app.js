import {EMPTY_MESSAGE, cookbookToggleView, formatResultCount, matchesRecipe} from './app-logic.js';

const COOKBOOK_URL = '/api/cookbook';
const COOKBOOK_ERROR = 'Could not update My Cookbook. Please try again.';
const STATUS_ID = 'cookbook-status';
const VISUALLY_HIDDEN = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap';

export function initSearch(doc) {
  const search = doc.querySelector('#search');
  const count = doc.querySelector('#count');
  const empty = doc.querySelector('#empty');
  if (!search || !count || !empty) return;
  const cards = [...doc.querySelectorAll('.recipe-card')];

  search.addEventListener('input', () => {
    let visible = 0;
    for (const card of cards) {
      const show = matchesRecipe(card.dataset.search, search.value);
      card.hidden = !show;
      visible += Number(show);
    }
    count.textContent = formatResultCount(visible);
    empty.textContent = EMPTY_MESSAGE;
    empty.hidden = visible !== 0;
  });
}

export function applyToggleView(button, view) {
  const icon = button.querySelector('.toggle-icon');
  const text = button.querySelector('.toggle-text');
  if (icon && text) {
    icon.textContent = view.icon;
    text.textContent = view.text;
  } else {
    button.textContent = `${view.icon} ${view.text}`;
  }
  button.setAttribute('aria-label', view.label);
  button.setAttribute('aria-pressed', String(view.pressed));
  button.classList.toggle('saved', view.pressed);
}

function statusRegion(doc) {
  let region = doc.getElementById(STATUS_ID);
  if (!region) {
    region = doc.createElement('p');
    region.id = STATUS_ID;
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', 'polite');
    region.setAttribute('style', VISUALLY_HIDDEN);
    doc.body.appendChild(region);
  }
  return region;
}

export function createCookbookHandler(doc, fetchFn = fetch) {
  return async function handleCookbookToggle(button) {
    if (button.getAttribute('aria-busy') === 'true') return;
    const id = button.dataset.recipeId;
    const title = button.dataset.recipeTitle ?? '';
    const wasSaved = button.getAttribute('aria-pressed') === 'true';
    const region = statusRegion(doc);
    region.textContent = '';
    button.setAttribute('aria-busy', 'true');
    applyToggleView(button, cookbookToggleView(title, !wasSaved));
    try {
      const response = await fetchFn(wasSaved ? `${COOKBOOK_URL}/${encodeURIComponent(id)}` : COOKBOOK_URL, {
        method: wasSaved ? 'DELETE' : 'POST',
        headers: {'Content-Type': 'application/json'},
        body: wasSaved ? undefined : JSON.stringify({id}),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
    } catch {
      applyToggleView(button, cookbookToggleView(title, wasSaved));
      region.textContent = COOKBOOK_ERROR;
    } finally {
      button.removeAttribute('aria-busy');
    }
  };
}

export function initCookbookToggles(doc, fetchFn = fetch) {
  const handler = createCookbookHandler(doc, fetchFn);
  for (const button of doc.querySelectorAll('.cookbook-toggle, [data-action=cookbook]')) {
    button.addEventListener('click', () => handler(button));
  }
  return handler;
}

export const cookbookHandler = initCookbookToggles(document);
initSearch(document);
