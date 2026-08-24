/**
 * The steps of the playlist flow, as the reader sees them.
 *
 * Not beside the page that draws the first one: a module exporting both a
 * component and a constant loses fast refresh, which `react-refresh`
 * enforces. Every step of the flow reads the same list.
 */

/** Four steps. Labels from `frontend/index.html:224`; order from `app.js:1070`. */
export const PLAYLIST_STEPS = ['Prompt', 'Refine', 'Filters', 'Results']
