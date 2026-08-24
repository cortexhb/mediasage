/**
 * What the refine step needs, and the check that it may be shown at all.
 *
 * The questions were bought by the prompt step, so a deep link with no flow
 * record behind it has nothing to draw and is sent back to step one. This is
 * where that precondition lives; the page itself expresses none.
 */
import { redirect } from 'react-router'

import type { PromptFlow } from '../flowStore/flowStore.ts'
import { readPlaylistFlow } from '../flowStore/flowStore.ts'

export function loadRefine(): PromptFlow | Response {
  const flow = readPlaylistFlow()
  // A seed flow has no questions to refine.
  if (flow?.mode !== 'prompt') return redirect('/playlist/prompt')

  return flow
}
