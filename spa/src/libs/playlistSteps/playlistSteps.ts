/**
 * The steps of a playlist flow, as the reader sees them.
 *
 * Not beside the page that draws the first one: a module exporting both a
 * component and a constant loses fast refresh, which `react-refresh`
 * enforces. Every step of the flow reads the same list.
 */
import type { FlowMode } from '../flowStore/flowStore.ts'

/**
 * Four steps, differing only in the second.
 *
 * Labels from `frontend/index.html:224`; the mode-dependent middle is
 * `app.js:1068`, where a prompt flow refines and a seed flow picks
 * dimensions.
 */
const STEPS: Readonly<Record<FlowMode, readonly string[]>> = {
  prompt: ['Prompt', 'Refine', 'Filters', 'Results'],
  seed: ['Seed', 'Dimensions', 'Filters', 'Results'],
}

export function playlistSteps(mode: FlowMode): readonly string[] {
  return STEPS[mode]
}
