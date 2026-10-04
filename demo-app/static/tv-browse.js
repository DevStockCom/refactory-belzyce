import {enterTarget, nextFocus} from './tv-nav.js';

const CARD = '.recipe-card';

export function focusAndReveal(element) {
  if (!element) return;
  element.focus({preventScroll: true});
  element.scrollIntoView({block: 'nearest', inline: 'nearest'});
}

const focusTarget = (card) => card.querySelector('a') ?? card;

export function initTvBrowse(doc) {
  const rails = [...doc.querySelectorAll('.tv-rail[data-rail]')].map((rail) => [...rail.querySelectorAll(CARD)]);
  const shape = rails.map((cards) => cards.length);
  const first = rails.findIndex((cards) => cards.length);
  if (first < 0) return;

  const positionOf = () => {
    const card = doc.activeElement?.closest?.(CARD);
    if (!card) return null;
    for (let rail = 0; rail < rails.length; rail += 1) {
      const index = rails[rail].indexOf(card);
      if (index >= 0) return {rail, index};
    }
    return null;
  };

  focusAndReveal(focusTarget(rails[first][0]));

  doc.addEventListener('keydown', (event) => {
    const current = positionOf();
    if (event.key === 'Enter') {
      if (!current) return;
      event.preventDefault();
      location.assign(enterTarget(rails[current.rail][current.index].dataset.recipeId));
      return;
    }
    const next = nextFocus(shape, current ?? {rail: first, index: 0}, event.key);
    if (!next) return;
    event.preventDefault();
    focusAndReveal(focusTarget(rails[next.rail][next.index]));
  });
}

initTvBrowse(document);
