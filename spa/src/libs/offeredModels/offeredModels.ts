/**
 * Which models a form shows for a server that may not hold the saved ones.
 *
 * Pure, and separated from the field that renders it because getting this
 * wrong overwrites a saved configuration: a name the server lacks becomes
 * empty rather than becoming the server's first model, so the save omits it
 * instead of replacing it. Mirrors `frontend/app.js:1847-1859`, where an
 * unknown value left the `<select>` empty and only a pair of empty selects
 * fell back to the first model.
 */
export interface ChosenModels {
  readonly analysis: string
  readonly generation: string
}

export function offeredModels(
  models: readonly string[],
  analysis: string,
  generation: string,
): ChosenModels {
  const held = (want: string) => (models.includes(want) ? want : '')
  const chosen = { analysis: held(analysis), generation: held(generation) }

  const first = models[0]
  if (
    chosen.analysis === '' &&
    chosen.generation === '' &&
    first !== undefined
  ) {
    return { analysis: first, generation: first }
  }
  return chosen
}
