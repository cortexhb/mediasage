/**
 * What leaving the filters step does: keep the selection, start generating.
 *
 * Everything selected is sent as nothing at all. `frontend/app.js:3061` did
 * the same, and the reason is not brevity: a genre filter listing every genre
 * still excludes the tracks that carry no genre at all.
 *
 * Generation starts here, in the submit, and nowhere else. Started from the
 * next page's effect it would run again on every reload of it, and each run
 * spends two LLM calls.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import type { ChosenFilters } from '../flowStore/flowStore.ts'
import { readPlaylistFlow, writePlaylistFlow } from '../flowStore/flowStore.ts'
import { formLast, formText } from '../formText/formText.ts'
import { generateBody } from '../generateBody/generateBody.ts'
import { startRun } from '../playlistRun/playlistRun.ts'
import { streamDeadline } from '../streamDeadline/streamDeadline.ts'

/** The chosen names, or nothing where every one of them was chosen. */
function narrowed(
  chosen: readonly string[],
  available: readonly string[],
): readonly string[] {
  return chosen.length === available.length ? [] : chosen
}

export async function chooseFilters({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<Response> {
  const flow = readPlaylistFlow()
  if (!flow?.analysis) return redirect('/playlist/prompt')

  const form = await request.formData()
  const filters: ChosenFilters = {
    genres: narrowed(
      form.getAll('genres').map(String),
      flow.analysis.available_genres.map((genre) => genre.name),
    ),
    decades: narrowed(
      form.getAll('decades').map(String),
      flow.analysis.available_decades.map((decade) => decade.name),
    ),
    track_count: Number(formText(form, 'track_count')),
    exclude_live: formLast(form, 'exclude_live') === 'true',
    min_rating: Number(formText(form, 'min_rating')),
    max_tracks_to_ai: Number(formText(form, 'max_tracks_to_ai')),
  }
  // The kept playlist is dropped: these filters are what replaces it.
  writePlaylistFlow({
    id: flow.id,
    prompt: flow.prompt,
    questions: flow.questions,
    refinementAnswers: flow.refinementAnswers,
    analysis: flow.analysis,
    filters,
  })

  startRun(
    generateBody(flow.id, flow.prompt, flow.refinementAnswers, filters),
    await streamDeadline(request.signal),
  )
  return redirect('/playlist/prompt/playlist')
}
