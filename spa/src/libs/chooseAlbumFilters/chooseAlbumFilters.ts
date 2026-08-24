/**
 * What leaving the album filters step does: keep the selection, start the
 * round.
 *
 * Everything selected is sent as nothing at all, as `frontend/app.js:4422`
 * sends it: a genre filter listing every genre still excludes the albums that
 * carry no genre. How many were on offer comes from the form, because the page
 * already knows the totals it drew.
 *
 * Generation starts here, in the submit, and nowhere else. Started from the
 * results page's effect it would run again on every reload of it.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import type {
  ChosenAlbumFilters,
  Familiarity,
  RecommendMode,
} from '../albumStore/albumStore.ts'
import { readAlbumFlow, writeAlbumFlow } from '../albumStore/albumStore.ts'
import { startRound } from '../albumRun/albumRun.ts'
import { keepFamiliarity } from '../familiarityPref/familiarityPref.ts'
import { formText } from '../formText/formText.ts'
import { narrowSelection } from '../narrowSelection/narrowSelection.ts'
import { roundBody } from '../roundBody/roundBody.ts'
import { streamDeadline } from '../streamDeadline/streamDeadline.ts'

export async function chooseAlbumFilters({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<Response> {
  const flow = readAlbumFlow()
  if (!flow) return redirect('/recommend')

  const form = await request.formData()
  const filters: ChosenAlbumFilters = {
    genres: narrowSelection(
      form.getAll('genres').map(String),
      Number(formText(form, 'genre_total')),
    ),
    decades: narrowSelection(
      form.getAll('decades').map(String),
      Number(formText(form, 'decade_total')),
    ),
    max_albums: Number(formText(form, 'max_albums')),
  }
  const familiarity = formText(form, 'familiarity') as Familiarity
  const mode = formText(form, 'mode') as RecommendMode

  // The kept result is dropped: this selection is what replaces it.
  const chosen = { ...flow, filters, familiarity, mode, result: undefined }
  writeAlbumFlow(chosen)
  keepFamiliarity(familiarity)

  const body = roundBody(chosen)
  if (body) startRound(body, await streamDeadline(request.signal))
  return redirect('/recommend/results')
}
