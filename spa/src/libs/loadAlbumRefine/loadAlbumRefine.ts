/**
 * What the album refine step needs, and the check that it may be shown at all.
 *
 * The questions and the session were bought by the prompt step, so a deep link
 * with no record behind it has nothing to draw and is sent back to step one.
 */
import { redirect } from 'react-router'

import type { AlbumFlow } from '../albumStore/albumStore.ts'
import { readAlbumFlow } from '../albumStore/albumStore.ts'

export function loadAlbumRefine(): AlbumFlow | Response {
  const flow = readAlbumFlow()
  if (!flow) return redirect('/recommend')

  return flow
}
