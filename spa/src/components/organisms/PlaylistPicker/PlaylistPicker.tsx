/**
 * Which existing playlist replace and append write into.
 *
 * Ports `#playlist-picker-container` (`frontend/index.html:414`). It stands
 * where the name field does, because legacy shows exactly one of the two
 * (`frontend/app.js:3613`): a new playlist is named, an existing one is
 * chosen.
 *
 * Mounted only while picking, so the list is read when the mode is chosen and
 * not before.
 */
import { useEffect, useState } from 'react'

import type { PlexPlaylistInfo } from '../../../api/generated/types.gen.ts'
import { listPlexPlaylists } from '../../../api/playlists/playlists.ts'
import { SCRATCH } from '../../../libs/savePlaylistToPlex/savePlaylistToPlex.ts'
import { Select } from '../../atoms/Select/Select.tsx'
import styles from './PlaylistPicker.module.scss'

export function PlaylistPicker() {
  const [playlists, setPlaylists] = useState<PlexPlaylistInfo[]>([])
  // Empty is the scratch playlist, which the backend creates on demand.
  const [chosen, setChosen] = useState('')

  useEffect(() => {
    const aborter = new AbortController()
    listPlexPlaylists(aborter.signal)
      .then(setPlaylists)
      .catch(() => undefined)
    return () => {
      aborter.abort()
    }
  }, [])

  const options = [
    { value: '', label: SCRATCH },
    ...playlists
      .filter((playlist) => playlist.title !== SCRATCH)
      .map((playlist) => ({
        value: playlist.rating_key,
        label: `${playlist.title} (${String(playlist.track_count)} tracks)`,
      })),
  ]
  const title =
    playlists.find((playlist) => playlist.rating_key === chosen)?.title ??
    SCRATCH

  return (
    <div className={styles.playlistPicker}>
      <Select
        name="playlist_id"
        aria-label="Select playlist to update"
        options={options}
        value={chosen}
        onChange={(event) => {
          setChosen(event.target.value)
        }}
      />
      {/* The save dialog names the playlist; the response does not carry it. */}
      <input type="hidden" name="playlist_name" value={title} />
    </div>
  )
}
