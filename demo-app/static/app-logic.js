export const EMPTY_MESSAGE = 'No recipes found. Try another ingredient or dish.';

export function matchesRecipe(searchText, query) {
  const needle = String(query ?? '').trim().toLowerCase();
  return String(searchText ?? '').toLowerCase().includes(needle);
}

export function formatResultCount(count) {
  return count === 1 ? '1 recipe' : `${count} recipes`;
}

export function toggleSavedIds(current, id) {
  const values = new Set(current ?? []);
  values.has(id) ? values.delete(id) : values.add(id);
  return [...values].sort();
}

export function cookbookToggleView(title, saved) {
  return saved
    ? {text: 'Saved', icon: '✓', label: `Remove ${title} from My Cookbook`, pressed: true}
    : {text: 'Save', icon: '+', label: `Save ${title} to My Cookbook`, pressed: false};
}
