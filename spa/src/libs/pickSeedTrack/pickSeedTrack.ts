/**
 * What picking a search result does: analyse the track, start the flow.
 *
 * An action because it spends an LLM call. `frontend/app.js:2930` did the
 * same work on a click, and the flow id is minted here for the same reason
 * the prompt step mints one -- everything this flow spends traces under it.
 *
 * The analysis answers the track as well as its dimensions, so the record is
 * written from the response rather than from the row that was clicked.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { analyzeTrack } from '../../api/analyze/analyze.ts'
import { explainError } from '../explainError/explainError.ts'
import { newFlowId } from '../flowId/flowId.ts'
import { writePlaylistFlow } from '../flowStore/flowStore.ts'
import { formText } from '../formText/formText.ts'

/** What the seed step renders when the analysis failed. */
export interface SeedActionResult {
  readonly error: string
}

export async function pickSeedTrack({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<Response | SeedActionResult> {
  const form = await request.formData()
  const ratingKey = formText(form, 'rating_key')
  if (!ratingKey) return { error: 'Pick a track to start from.' }

  const id = newFlowId()
  try {
    const analysed = await analyzeTrack(ratingKey, id, request.signal)
    writePlaylistFlow({
      mode: 'seed',
      id,
      track: analysed.track,
      dimensions: analysed.dimensions,
    })
  } catch (error) {
    return { error: explainError(error) }
  }

  return redirect('/playlist/seed/dimensions')
}
