/**
 * The save button on `/result/:resultId`, for whichever shape the result is.
 *
 * One action, because a route has one, and the page renders either a playlist
 * or an album. `intent=album` is what the album branch's form carries; a
 * playlist's form carries the fields `libs/savePlaylistToPlex` already reads.
 *
 * Neither path needs a session or a flow record: a saved result has neither,
 * and both saves are assembled from the form.
 */
import type { ActionFunctionArgs } from 'react-router'

import { formText } from '../formText/formText.ts'
import type { AlbumSaveResult } from '../saveAlbumToPlex/saveAlbumToPlex.ts'
import { saveAlbumToPlex } from '../saveAlbumToPlex/saveAlbumToPlex.ts'
import type { SaveResult } from '../savePlaylistToPlex/savePlaylistToPlex.ts'
import { savePlaylistToPlex } from '../savePlaylistToPlex/savePlaylistToPlex.ts'

export type ResultSaveAction = AlbumSaveResult | SaveResult

export async function saveResultToPlex({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<ResultSaveAction> {
  // Cloned: `savePlaylistToPlex` reads the body itself, and it is read once.
  const form = await request.clone().formData()

  if (formText(form, 'intent') === 'album')
    return await saveAlbumToPlex(form, request.signal)

  return await savePlaylistToPlex({ request })
}
