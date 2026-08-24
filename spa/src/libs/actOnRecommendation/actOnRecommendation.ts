/**
 * The three things the album results step can do, all of which spend or write.
 *
 * One action, keyed on `intent`, because a route has one: saving an album to
 * Plex, generating another round on the same session, and switching that
 * session to discovery. Each is a click, never an effect.
 *
 * `again` and `discovery` answer a redirect back to the results step rather
 * than a result: what they start arrives on the stream, which the page is
 * already watching.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { savePlaylist } from '../../api/playlists/playlists.ts'
import { switchRecommendMode } from '../../api/recommend/recommend.ts'
import { startRound } from '../albumRun/albumRun.ts'
import type { AlbumFlow } from '../albumStore/albumStore.ts'
import { readAlbumFlow, writeAlbumFlow } from '../albumStore/albumStore.ts'
import { explainError } from '../explainError/explainError.ts'
import { formText } from '../formText/formText.ts'
import { roundBody } from '../roundBody/roundBody.ts'
import { streamDeadline } from '../streamDeadline/streamDeadline.ts'

/** What the results step renders after a save. */
export interface AlbumResultAction {
  readonly saved?: string
  readonly error?: string
}

const SAVE_FAILED = 'Failed to save playlist'

export async function actOnRecommendation({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<Response | AlbumResultAction> {
  const form = await request.formData()
  const intent = formText(form, 'intent')

  const flow = readAlbumFlow()
  if (!flow) return redirect('/recommend')

  if (intent === 'save') return await saved(form, request.signal)

  if (intent === 'discovery') {
    try {
      const switched = await switchRecommendMode(
        { session_id: flow.sessionId, mode: 'discovery' },
        request.signal,
      )
      const moved = {
        ...flow,
        sessionId: switched.session_id,
        mode: 'discovery' as const,
        result: undefined,
      }
      writeAlbumFlow(moved)
      await run(moved, request.signal)
    } catch (error) {
      return { error: explainError(error) }
    }
    return redirect('/recommend/results')
  }

  // `again`: the same session, which is what excludes what it already showed.
  await run({ ...flow, result: undefined }, request.signal)
  return redirect('/recommend/results')
}

/** Start a round from the record, where it holds enough to ask for one. */
async function run(flow: AlbumFlow, signal: AbortSignal): Promise<void> {
  const body = roundBody(flow)
  if (body) startRound(body, await streamDeadline(signal))
}

/**
 * Write one album's tracks to a new Plex playlist.
 *
 * `frontend/app.js:5022` names it `Recommended: <album> - <artist>` and puts
 * the pitch in the description.
 */
async function saved(
  form: FormData,
  signal: AbortSignal,
): Promise<AlbumResultAction> {
  const keys = form.getAll('rating_keys').map(String)
  if (!keys.length) return { error: 'That album has no tracks in your library' }

  const album = formText(form, 'album')
  const artist = formText(form, 'artist')

  try {
    const result = await savePlaylist(
      {
        name: `Recommended: ${album} - ${artist}`,
        rating_keys: keys,
        description: formText(form, 'pitch'),
      },
      signal,
    )
    if (!result.success) return { error: result.error ?? SAVE_FAILED }
    return { saved: `Saved "${album}" to playlist` }
  } catch (error) {
    return { error: explainError(error) }
  }
}
