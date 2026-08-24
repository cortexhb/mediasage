/**
 * What the album filters step needs, and the check that it may be shown at all.
 *
 * A step reached without a record, or before the questions were answered, is
 * sent back to where that happens. Those are the only preconditions the step
 * expresses.
 *
 * What starts selected is the suggestion where there is one, and everything
 * otherwise -- `frontend/app.js:4253` falls back to every name, and every name
 * selected is sent as no filter at all.
 *
 * The library is read live, not from the cache: the suggestion was made from
 * the live list (`libs/suggestionCache`), and the cache's normalised genres
 * are a different set of names.
 */
import type { LoaderFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { readConfig } from '../../api/config/config.ts'
import type { DecadeCount, GenreCount } from '../../api/generated/types.gen.ts'
import { readLibraryStats } from '../../api/library/library.ts'
import type { Familiarity, RecommendMode } from '../albumStore/albumStore.ts'
import { readAlbumFlow } from '../albumStore/albumStore.ts'

/** What `frontend/app.js:1284` falls back to when none is configured. */
const CEILING = 2500

export interface AlbumFiltersData {
  readonly availableGenres: readonly GenreCount[]
  readonly availableDecades: readonly DecadeCount[]
  readonly selectedGenres: readonly string[]
  readonly selectedDecades: readonly string[]
  /** Whether a suggestion made the selection, which the banner announces. */
  readonly fromPrompt: boolean
  /** The most albums this model can be sent, `config.max_albums_to_ai`. */
  readonly ceiling: number
  readonly mode: RecommendMode
  readonly familiarity: Familiarity
}

export async function loadAlbumFilters({
  request,
}: Pick<LoaderFunctionArgs, 'request'>): Promise<AlbumFiltersData | Response> {
  const flow = readAlbumFlow()
  if (!flow) return redirect('/recommend')
  if (!flow.answers) return redirect('/recommend/refine')

  const [{ genres, decades }, ceiling] = await Promise.all([
    readLibraryStats(request.signal),
    limit(request.signal),
  ])

  const suggested = flow.suggested
  return {
    availableGenres: genres,
    availableDecades: decades,
    selectedGenres: suggested?.genres ?? genres.map((genre) => genre.name),
    selectedDecades: suggested?.decades ?? decades.map((decade) => decade.name),
    fromPrompt: Boolean(suggested),
    ceiling,
    mode: flow.mode,
    familiarity: flow.familiarity,
  }
}

/** The album ceiling, or the default where the configuration cannot be read. */
async function limit(signal: AbortSignal): Promise<number> {
  try {
    const config = await readConfig(signal)
    return config.max_albums_to_ai || CEILING
  } catch {
    // The step stays usable; only the limit options lose their ceiling.
    return CEILING
  }
}
