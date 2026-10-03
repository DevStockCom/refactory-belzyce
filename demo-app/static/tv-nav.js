/** @typedef {number[]} RailShape Card count of each rail, in DOM order. */
/** @typedef {{rail: number, index: number}} FocusPosition */
/** @typedef {'back' | 'cookbook'} DetailAction */

export const TV_HOME_URL = '/?mode=tv';

/** @type {DetailAction[]} */
export const DETAIL_ACTIONS = ['back', 'cookbook'];

/**
 * @param {RailShape} shape
 * @param {FocusPosition} current
 * @param {string} key
 * @returns {FocusPosition | null} null for unhandled keys; current when no move is possible.
 */
export function nextFocus(shape, current, key) {
  const rails = Array.isArray(shape) ? shape : [];
  const position = current ?? {rail: 0, index: 0};
  const {rail, index} = position;
  const length = (i) => (rails[i] > 0 ? rails[i] : 0);
  if (key === 'ArrowLeft' || key === 'ArrowRight') {
    const size = length(rail);
    if (!size) return position;
    const next = Math.min(size - 1, Math.max(0, index + (key === 'ArrowRight' ? 1 : -1)));
    return {rail, index: next};
  }
  if (key === 'ArrowUp' || key === 'ArrowDown') {
    const step = key === 'ArrowDown' ? 1 : -1;
    for (let i = rail + step; i >= 0 && i < rails.length; i += step) {
      if (length(i)) return {rail: i, index: Math.min(index, length(i) - 1)};
    }
    return position;
  }
  return null;
}

/** @param {string} recipeId */
export function enterTarget(recipeId) {
  return `/recipe/${encodeURIComponent(recipeId)}?mode=tv`;
}

/**
 * @param {DetailAction[]} actions
 * @param {DetailAction} current
 * @param {string} key
 * @returns {DetailAction | null}
 */
export function detailNext(actions, current, key) {
  if (key !== 'ArrowUp' && key !== 'ArrowDown') return null;
  const list = Array.isArray(actions) ? actions : [];
  const at = list.indexOf(current);
  if (at < 0) return list[0] ?? null;
  const next = Math.min(list.length - 1, Math.max(0, at + (key === 'ArrowDown' ? 1 : -1)));
  return list[next];
}

/** @param {string} key */
export function detailExit(key) {
  return key === 'Escape' || key === 'Backspace' ? TV_HOME_URL : null;
}
