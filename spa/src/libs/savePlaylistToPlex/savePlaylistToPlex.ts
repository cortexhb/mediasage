/**
 * Writing the generated playlist to Plex, in the mode that was chosen.
 *
 * An action, not a loader: it writes to the library. The tracks come in as
 * hidden fields rather than from the run, because an action has no access to
 * the page's state and the reader may have removed some.
 *
 * `frontend/app.js:3193`: a response that is not `success` carries its own
 * message, and a partial write still counts as saved.
 */
import type { ActionFunctionArgs } from 'react-router'

import { savePlaylist, updatePlaylist } from '../../api/playlists/playlists.ts'
import { explainError } from '../explainError/explainError.ts'
import { formText } from '../formText/formText.ts'

/** The playlist the backend writes to when no existing one is picked. */
export const SCRATCH = 'MediaSage - Now Playing'

export interface SaveResult {
  /** What the reader is told it did, for the dialog that follows. */
  readonly saved?: {
    /** Picks the dialog: `frontend/index.html:497` is a separate modal. */
    readonly updated: boolean
    /** Composed here, as `frontend/app.js:2166` and `:3665` compose theirs. */
    readonly summary: string
    readonly url?: string | null | undefined
  }
  readonly error?: string
}

const SAVE_FAILED = 'Failed to save playlist'

export async function savePlaylistToPlex({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<SaveResult> {
  const form = await request.formData()
  const keys = form
    .getAll('rating_keys')
    .filter((key) => typeof key === 'string')
  if (!keys.length) return { error: 'Playlist is empty' }

  const description = formText(form, 'description')
  const mode = formText(form, 'mode')

  if (mode === 'replace' || mode === 'append') {
    return written(form, keys, description, mode, request.signal)
  }

  const name = formText(form, 'name').trim()
  if (!name) return { error: 'Please enter a playlist name' }

  try {
    const result = await savePlaylist(
      { name, rating_keys: keys, description },
      request.signal,
    )
    if (!result.success) return { error: result.error ?? SAVE_FAILED }

    const added = result.tracks_added ?? keys.length
    return {
      saved: {
        updated: false,
        summary: `"${name}" with ${String(added)} track${added === 1 ? '' : 's'} has been added to your Plex library.`,
        url: result.playlist_url,
      },
    }
  } catch (error) {
    return { error: explainError(error) }
  }
}

/** The replace and append modes, which write into a playlist that exists. */
async function written(
  form: FormData,
  keys: string[],
  description: string,
  mode: 'replace' | 'append',
  signal: AbortSignal,
): Promise<SaveResult> {
  // Empty is the scratch playlist, which the backend creates on demand.
  const playlist = formText(form, 'playlist_id')

  try {
    const result = await updatePlaylist(
      {
        playlist_id: playlist,
        rating_keys: keys,
        mode,
        description,
      },
      signal,
    )
    if (!result.success) return { error: result.error ?? SAVE_FAILED }

    const title = playlist
      ? formText(form, 'playlist_name') || 'Playlist'
      : SCRATCH
    const added = String(result.tracks_added ?? keys.length)
    const skipped = result.duplicates_skipped ?? 0

    let summary =
      mode === 'append'
        ? `Updated ${title} — Added ${added} tracks`
        : `Updated ${title} — Replaced with ${added} tracks`
    if (mode === 'append' && skipped)
      summary += ` (${String(skipped)} duplicates skipped)`
    if (result.warning) summary += ` ⚠ ${result.warning}`

    return { saved: { updated: true, summary, url: result.playlist_url } }
  } catch (error) {
    return { error: explainError(error) }
  }
}
