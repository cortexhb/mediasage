/**
 * What the dimensions step needs, and the check that it may be shown at all.
 *
 * The track and its dimensions were bought by the seed step, so a deep link
 * with no seed flow behind it has nothing to draw and is sent back to step
 * one. A prompt flow lands there too: it has no track to explore.
 */
import { redirect } from 'react-router'

import type { SeedFlow } from '../flowStore/flowStore.ts'
import { readPlaylistFlow } from '../flowStore/flowStore.ts'

export function loadDimensions(): SeedFlow | Response {
  const flow = readPlaylistFlow()
  if (flow?.mode !== 'seed') return redirect('/playlist/seed')

  return flow
}
