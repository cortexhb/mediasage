/**
 * What the album results step needs, and the check that it may be shown at all.
 *
 * A step reached with no filters chosen has nothing to generate from, so it is
 * sent back to where they are chosen. Nothing is read from the network: the
 * round arrives on a stream the filters step started, and a reload redraws the
 * one kept in the record rather than buying another.
 */
import { redirect } from 'react-router'

import type { AlbumFlow } from '../albumStore/albumStore.ts'
import { readAlbumFlow } from '../albumStore/albumStore.ts'

export function loadAlbumResults(): AlbumFlow | Response {
  const flow = readAlbumFlow()
  if (!flow) return redirect('/recommend')
  if (!flow.filters) return redirect('/recommend/filters')

  return flow
}
