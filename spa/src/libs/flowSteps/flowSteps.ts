/**
 * The steps of a flow, as the reader sees them.
 *
 * Not beside the page that draws the first one: a module exporting both a
 * component and a constant loses fast refresh, which `react-refresh` enforces.
 * Every step of every flow reads its list from here.
 *
 * Labels from `frontend/index.html:224`; the mode-dependent middle is
 * `app.js:1068`, where a prompt flow refines and a seed flow picks dimensions.
 * The album flow's four are the same four (`frontend/index.html:524` labels
 * its third "Filters" while the panel is `rec-step-setup`; the label is what a
 * reader sees, so it is what is kept).
 */
import type { FlowMode } from '../flowStore/flowStore.ts'

const PROMPT_STEPS: readonly string[] = [
  'Prompt',
  'Refine',
  'Filters',
  'Results',
]

const SEED_STEPS: readonly string[] = [
  'Seed',
  'Dimensions',
  'Filters',
  'Results',
]

const STEPS: Readonly<Record<FlowMode, readonly string[]>> = {
  prompt: PROMPT_STEPS,
  seed: SEED_STEPS,
}

export function playlistSteps(mode: FlowMode): readonly string[] {
  return STEPS[mode]
}

/** The album flow's steps, which read the same as a prompt flow's. */
export const ALBUM_STEPS = PROMPT_STEPS
