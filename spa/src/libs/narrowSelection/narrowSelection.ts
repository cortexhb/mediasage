/**
 * What a chip selection means once everything in it is selected: nothing.
 *
 * `frontend/app.js:3061` and `:4422` both send no filter where every name was
 * chosen, and the reason is not brevity: a genre filter listing every genre
 * still excludes the rows that carry no genre at all.
 *
 * Both filters actions narrow their genres and their decades this way.
 */

/** The chosen names, or nothing where every one of them was chosen. */
export function narrowSelection(
  chosen: readonly string[],
  available: number,
): readonly string[] {
  return chosen.length === available ? [] : chosen
}
