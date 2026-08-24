/**
 * A playlist's tracks, its name, and what may be done with them.
 *
 * The legacy results grid (`frontend/index.html:404`): the name and narrative
 * above the tracks, the actions and the reason panel beside them. The live
 * step and a saved result drew the same DOM, so they draw the same component
 * here; what differs is that a snapshot has no track to remove and no run to
 * start over, which is `onRemove` and `children`.
 *
 * Selecting a track is what fills the reason panel, which is why the rows are
 * a listbox and why the selection is held here rather than by the page.
 *
 * The `Form` is this component's, so what is submitted is what is drawn; the
 * action it posts to belongs to whichever route drew it.
 */
import type { ReactNode } from 'react'
import { useState } from 'react'
import { Form } from 'react-router'

import type { Track } from '../../../api/generated/types.gen.ts'
import { TrackRow } from '../../molecules/TrackRow/TrackRow.tsx'
import { PlayNow } from '../PlayNow/PlayNow.tsx'
import { PlaylistPicker } from '../PlaylistPicker/PlaylistPicker.tsx'
import type { SaveMode } from '../SavePlaylist/SavePlaylist.tsx'
import { SavePlaylist } from '../SavePlaylist/SavePlaylist.tsx'
import { TrackReasonPanel } from '../TrackReasonPanel/TrackReasonPanel.tsx'
import styles from './PlaylistResultGrid.module.scss'

export interface PlaylistResultGridProps {
  /** What the name field holds: the model's title, or what was typed over it. */
  readonly name: string
  readonly onName: (name: string) => void
  readonly narrative: string
  /** The request that produced this, where there was one to quote. */
  readonly prompt?: string | undefined
  readonly tracks: readonly Track[]
  readonly reasons: Readonly<Record<string, string>> | undefined
  /** Names the track list for assistive technology. */
  readonly label: string
  readonly mode: SaveMode
  readonly onMode: (mode: SaveMode) => void
  /** Absent on a snapshot: what was saved is not the reader's to edit. */
  readonly onRemove?: ((ratingKey: string) => void) | undefined
  /** Actions under Save and Play, e.g. starting the flow over. */
  readonly children?: ReactNode
}

export function PlaylistResultGrid({
  name,
  onName,
  narrative,
  prompt,
  tracks,
  reasons,
  label,
  mode,
  onMode,
  onRemove,
  children,
}: PlaylistResultGridProps) {
  const [chosen, setChosen] = useState<string | null>(null)

  // The first track until one is picked, as `frontend/app.js:1673` did it.
  const selected =
    tracks.find((track) => track.rating_key === chosen) ?? tracks[0]
  const count = `♫ ${String(tracks.length)} track${tracks.length === 1 ? '' : 's'}`

  return (
    <Form method="post" className={styles.playlistResultGrid}>
      <div className={styles.playlistResultGrid__header}>
        {/* Not an `Input`: this one is the page title as well as a field. */}
        {mode === 'new' ? (
          <input
            type="text"
            name="name"
            className={styles.playlistResultGrid__name}
            value={name}
            onChange={(event) => {
              onName(event.target.value)
            }}
            placeholder="Enter playlist name..."
            aria-label="Playlist name"
          />
        ) : (
          <PlaylistPicker />
        )}
        {narrative && (
          <p className={styles.playlistResultGrid__narrative}>{narrative}</p>
        )}
        <div className={styles.playlistResultGrid__meta}>
          <span className={styles.playlistResultGrid__pill}>{count}</span>
          {/* A seed flow has no request to quote, so it draws none. */}
          {prompt && (
            <span className={styles.playlistResultGrid__prompt}>{prompt}</span>
          )}
        </div>
      </div>

      <div className={styles.playlistResultGrid__sidebar}>
        <div className={styles.playlistResultGrid__actions}>
          <input type="hidden" name="description" value={narrative} />
          {tracks.map((track) => (
            <input
              key={track.rating_key}
              type="hidden"
              name="rating_keys"
              value={track.rating_key}
            />
          ))}
          <SavePlaylist
            mode={mode}
            onMode={onMode}
            count={tracks.length}
            disabled={!tracks.length}
          />
          <PlayNow ratingKeys={tracks.map((track) => track.rating_key)} />
          {children}
        </div>
        <TrackReasonPanel
          track={selected}
          reason={selected && reasons?.[selected.rating_key]}
        />
      </div>

      <div
        className={styles.playlistResultGrid__tracks}
        role="listbox"
        aria-label={label}
      >
        {tracks.map((track, index) => (
          <TrackRow
            key={track.rating_key}
            track={track}
            position={index + 1}
            selected={selected?.rating_key === track.rating_key}
            onChoose={() => {
              setChosen(track.rating_key)
            }}
            onRemove={() => {
              onRemove?.(track.rating_key)
            }}
          />
        ))}
      </div>
    </Form>
  )
}
