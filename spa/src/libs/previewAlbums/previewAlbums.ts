/**
 * How many albums a selection reaches.
 *
 * A resource route rather than a call from inside the page: the filters step
 * asks again on every click, and a fetcher keeps those reads off the
 * navigation entirely. `libs/previewSelection` says more about why.
 *
 * A loader, not an action: `GET /api/recommend/albums/preview` counts rows in
 * the local cache and its whole request fits in a query string.
 */
import type { LoaderFunctionArgs } from 'react-router'

import type { AlbumPreviewResponse } from '../../api/generated/types.gen.ts'
import { previewRecommendAlbums } from '../../api/recommend/recommend.ts'

/** Named once: the route and the fetcher's URL must agree. */
export const ALBUM_PREVIEW = '/recommend/albums/preview'

/** What `frontend/app.js:1284` falls back to when none is configured. */
const CEILING = 2500

/**
 * The count, or nothing.
 *
 * A failure answers nothing rather than faulting: the line it fills is
 * informational, and the step stays usable without it.
 */
export async function previewAlbums({
  request,
}: Pick<LoaderFunctionArgs, 'request'>): Promise<AlbumPreviewResponse | null> {
  const asked = new URL(request.url).searchParams
  const genres = asked.get('genres')
  const decades = asked.get('decades')

  try {
    return await previewRecommendAlbums(
      {
        genres: genres ?? undefined,
        decades: decades ?? undefined,
        max_albums: Number(asked.get('max_albums')) || CEILING,
      },
      request.signal,
    )
  } catch {
    return null
  }
}
