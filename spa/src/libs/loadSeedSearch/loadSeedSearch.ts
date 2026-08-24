/**
 * The tracks a seed search found, from the query in the URL.
 *
 * A loader rather than an action: searching Plex reads, costs no LLM call and
 * is idempotent, so it belongs in the address bar -- a reload repeats it and a
 * back from the dimensions step returns to the results already on screen.
 *
 * A failed search is returned, not thrown. The step stays usable with its box
 * still filled, where an error boundary would replace the whole page.
 */
import type { LoaderFunctionArgs } from 'react-router'

import type { Track } from '../../api/generated/types.gen.ts'
import { searchTracks } from '../../api/library/library.ts'
import { explainError } from '../explainError/explainError.ts'

export interface SeedSearchData {
  /** What was searched for, to keep the box filled across the reload. */
  readonly query: string
  readonly tracks: readonly Track[]
  readonly error?: string | undefined
}

export async function loadSeedSearch({
  request,
}: Pick<LoaderFunctionArgs, 'request'>): Promise<SeedSearchData> {
  const query = new URL(request.url).searchParams.get('q')?.trim() ?? ''
  if (!query) return { query: '', tracks: [] }

  try {
    return { query, tracks: await searchTracks(query, request.signal) }
  } catch (error) {
    return { query, tracks: [], error: explainError(error) }
  }
}
