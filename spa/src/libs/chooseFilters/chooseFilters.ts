/**
 * What leaving the filters step does: keep the selection, start generating.
 *
 * Everything selected is sent as nothing at all. `frontend/app.js:3061` did
 * the same, and the reason is not brevity: a genre filter listing every genre
 * still excludes the tracks that carry no genre at all.
 *
 * How many were on offer comes from the form rather than from the record: the
 * step is shared by both flows, which come by their lists differently, and
 * the page already knows the totals it drew.
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
import { narrowSelection } from '../narrowSelection/narrowSelection.ts'
import { startRun } from '../playlistRun/playlistRun.ts'
import { streamDeadline } from '../streamDeadline/streamDeadline.ts'

export async function chooseFilters({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<Response> {
  const flow = readPlaylistFlow()
  if (!flow) return redirect('/playlist/prompt')

  const form = await request.formData()
  const filters: ChosenFilters = {
    genres: narrowSelection(
      form.getAll('genres').map(String),
      Number(formText(form, 'genre_total')),
    ),
    decades: narrowSelection(
      form.getAll('decades').map(String),
      Number(formText(form, 'decade_total')),
    ),
    track_count: Number(formText(form, 'track_count')),
    exclude_live: formLast(form, 'exclude_live') === 'true',
    min_rating: Number(formText(form, 'min_rating')),
    max_tracks_to_ai: Number(formText(form, 'max_tracks_to_ai')),
  }
  // The kept playlist is dropped: these filters are what replaces it.
  const started = { ...flow, filters, playlist: undefined }
  writePlaylistFlow(started)

  startRun(generateBody(started, filters), await streamDeadline(request.signal))
  return redirect(`/playlist/${flow.mode}/playlist`)
}
