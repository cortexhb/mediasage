/**
 * The four steps of the album flow, as the progress bar names them.
 *
 * `frontend/index.html:524` labels the third one "Filters" while its panel is
 * `rec-step-setup`; the label is what a reader sees, so it is what is kept.
 */

export const ALBUM_STEPS: readonly string[] = [
  'Prompt',
  'Refine',
  'Filters',
  'Results',
]
