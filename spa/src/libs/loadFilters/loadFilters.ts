/**
 * What the filters step needs, and the check that it may be shown at all.
 *
 * The genres and decades came back with the analysis, so nothing is read for
 * them: a step reached without one has nothing to draw and is sent back to
 * where it is bought. The record is also where a reload finds it.
 *
 * The configuration is read, and it is cheap and idempotent: the no-limit
 * button names the ceiling the context window allows (`frontend/app.js:1454`).
 */
import type { LoaderFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { readConfig } from '../../api/config/config.ts'
import type { AnalyzePromptResponse } from '../../api/generated/types.gen.ts'
import { readPlaylistFlow } from '../flowStore/flowStore.ts'

/** What `frontend/app.js:1455` falls back to when none is configured. */
const CEILING = 3500

export interface FiltersData {
  readonly analysis: AnalyzePromptResponse
  readonly ceiling: number
}

export async function loadFilters({
  request,
}: Pick<LoaderFunctionArgs, 'request'>): Promise<FiltersData | Response> {
  const flow = readPlaylistFlow()
  if (!flow) return redirect('/playlist/prompt')
  // Missing only when the analysis failed on the step before.
  if (!flow.analysis) return redirect('/playlist/prompt/refine')

  try {
    const config = await readConfig(request.signal)
    return {
      analysis: flow.analysis,
      ceiling: config.max_tracks_to_ai || CEILING,
    }
  } catch {
    // The step stays usable; only the no-limit label loses its ceiling.
    return { analysis: flow.analysis, ceiling: CEILING }
  }
}
