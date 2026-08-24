/**
 * Writing one recommended album's tracks to a new Plex playlist.
 *
 * Everything it needs comes off the form, so it works with no session behind
 * it -- which is what lets `/result/:resultId` offer the same button as the
 * live results step.
 */
import { savePlaylist } from '../../api/playlists/playlists.ts'
import { explainError } from '../explainError/explainError.ts'
import { formText } from '../formText/formText.ts'

/** What a page renders after a save. */
export interface AlbumSaveResult {
  readonly saved?: string
  readonly error?: string
}

const SAVE_FAILED = 'Failed to save playlist'

/**
 * `frontend/app.js:5022` names it `Recommended: <album> - <artist>` and puts
 * the pitch in the description.
 */
export async function saveAlbumToPlex(
  form: FormData,
  signal: AbortSignal,
): Promise<AlbumSaveResult> {
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
