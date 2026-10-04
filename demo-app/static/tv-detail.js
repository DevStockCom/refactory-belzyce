import {cookbookHandler} from './app.js';
import {detailExit, detailNext} from './tv-nav.js';
import {focusAndReveal} from './tv-browse.js';

export function initTvDetail(doc, onCookbook = cookbookHandler) {
  const elements = [...doc.querySelectorAll('[data-action]')];
  if (!elements.length) return;
  const byAction = new Map(elements.map((el) => [el.dataset.action, el]));
  const actions = [...byAction.keys()];
  const currentAction = () => actions.find((a) => byAction.get(a) === doc.activeElement);

  focusAndReveal(elements[0]);

  doc.addEventListener('keydown', (event) => {
    const exit = detailExit(event.key);
    if (exit) {
      event.preventDefault();
      location.assign(exit);
      return;
    }
    if (event.key === 'Enter') {
      const action = currentAction();
      if (!action) return;
      event.preventDefault();
      if (action === 'cookbook') onCookbook(byAction.get(action));
      else byAction.get(action).click();
      return;
    }
    const next = detailNext(actions, currentAction(), event.key);
    if (!next) return;
    event.preventDefault();
    focusAndReveal(byAction.get(next));
  });
}

initTvDetail(document);
