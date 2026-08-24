/**
 * What the playlist step needs, and the check that it may be shown at all.
 *
 * A step reached with no filters chosen has nothing to generate from, so it is
 * sent back to where they are chosen. Nothing is read from the network: the
 * playlist itself arrives on a stream the filters step started, and a reload
 * redraws the one kept in the record rather than buying another.
 */
import { redirect } from 'react-router'

import type { PlaylistFlow } from '../flowStore/flowStore.ts'
import { readPlaylistFlow } from '../flowStore/flowStore.ts'

export function loadPlaylist(): PlaylistFlow | Response {
  const flow = readPlaylistFlow()
  if (!flow) return redirect('/playlist/prompt')
  if (!flow.filters) return redirect('/playlist/prompt/filters')

  return flow
}
