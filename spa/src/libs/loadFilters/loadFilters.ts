/**
 * What the filters step needs, and the check that it may be shown at all.
 *
 * Shared by both flows, which is why nothing here is shaped like either one:
 * a prompt flow already holds the genres and decades in the analysis it
 * bought, and a seed flow reads them from the library instead. Both arrive as
 * the same four lists.
 *
 * A step reached without a record has nothing to draw and is sent back to
 * where the record is bought. That, and the mode in the URL matching the one
 * in the record, are the only preconditions the step expresses.
 *
 * The configuration is read, and it is cheap and idempotent: the no-limit
 * button names the ceiling the context window allows (`frontend/app.js:1454`).
 */
import type { LoaderFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { readConfig } from '../../api/config/config.ts'
import type { DecadeCount, GenreCount } from '../../api/generated/types.gen.ts'
import { readLibraryStats } from '../../api/library/library.ts'
import type { FlowMode, PlaylistFlow } from '../flowStore/flowStore.ts'
import { readPlaylistFlow } from '../flowStore/flowStore.ts'

/** What `frontend/app.js:1455` falls back to when none is configured. */
const CEILING = 3500

export interface FiltersData {
  readonly mode: FlowMode
  readonly availableGenres: readonly GenreCount[]
  readonly availableDecades: readonly DecadeCount[]
  /** Preselected on arrival; every available name, for a seed flow. */
  readonly suggestedGenres: readonly string[]
  readonly suggestedDecades: readonly string[]
  readonly ceiling: number
}

/** Where a flow missing what this step needs is sent back to. */
function backTo(mode: FlowMode): string {
  return mode === 'seed' ? '/playlist/seed' : '/playlist/prompt'
}

/**
 * The four lists this step draws, however the flow came by them.
 *
 * A prompt flow with no analysis behind it answers nothing: it has not
 * finished the step that buys them.
 */
async function choices(
  flow: PlaylistFlow,
  signal: AbortSignal,
): Promise<Omit<FiltersData, 'ceiling'> | undefined> {
  if (flow.mode === 'prompt') {
    const analysis = flow.analysis
    if (!analysis) return undefined
    return {
      mode: 'prompt',
      availableGenres: analysis.available_genres,
      availableDecades: analysis.available_decades,
      suggestedGenres: analysis.suggested_genres,
      suggestedDecades: analysis.suggested_decades,
    }
  }

  // Live Plex, not the cache: `analysis.py:43` builds the prompt flow's list
  // the same way, and the cache's normalised genres are a different set.
  const { genres, decades } = await readLibraryStats(signal)
  return {
    mode: 'seed',
    availableGenres: genres,
    availableDecades: decades,
    suggestedGenres: genres.map((genre) => genre.name),
    suggestedDecades: decades.map((decade) => decade.name),
  }
}

export async function loadFilters({
  params,
  request,
}: Pick<LoaderFunctionArgs, 'params' | 'request'>): Promise<
  FiltersData | Response
> {
  const flow = readPlaylistFlow()
  if (!flow) return redirect(backTo(params.mode === 'seed' ? 'seed' : 'prompt'))
  // A seed flow reached under /playlist/prompt/filters would draw the wrong
  // lists and generate from the wrong half of the request.
  if (flow.mode !== params.mode) return redirect(backTo(flow.mode))

  const drawn = await choices(flow, request.signal)
  if (!drawn) return redirect('/playlist/prompt/refine')

  try {
    const config = await readConfig(request.signal)
    return { ...drawn, ceiling: config.max_tracks_to_ai || CEILING }
  } catch {
    // The step stays usable; only the no-limit label loses its ceiling.
    return { ...drawn, ceiling: CEILING }
  }
}
