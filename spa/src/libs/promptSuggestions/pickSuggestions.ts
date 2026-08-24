/**
 * Choosing which suggestions to show, and which to show next.
 *
 * One per group, so the row on screen spans mood, activity, era, genre and
 * tempo rather than five variations of one idea (`frontend/app.js:4020`).
 *
 * The shuffle prefers a suggestion the reader has not just seen; a group with
 * nothing left falls back to its whole set rather than freezing.
 *
 * The groups are a parameter: the playlist flow and the album flow each own a
 * set (`libs/promptSuggestions`, `libs/albumSuggestions`) and pick from it the
 * same way.
 */

/** A set of suggestions, one of which is offered at a time. */
export type SuggestionGroups = readonly (readonly string[])[]

/** One at random from `pool`, which must not be empty. */
function anyOf(pool: readonly string[]): string {
  return pool[Math.floor(Math.random() * pool.length)] ?? ''
}

/** One suggestion per group. */
export function pickSuggestions(groups: SuggestionGroups): string[] {
  return groups.map((group) => anyOf(group))
}

/** One per group again, avoiding what is on screen where a group allows it. */
export function nextSuggestions(
  groups: SuggestionGroups,
  shown: readonly string[],
): string[] {
  const seen = new Set(shown)

  return groups.map((group) => {
    const unseen = group.filter((suggestion) => !seen.has(suggestion))
    return anyOf(unseen.length > 0 ? unseen : group)
  })
}
