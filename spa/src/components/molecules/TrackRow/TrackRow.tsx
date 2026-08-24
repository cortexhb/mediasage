/**
 * One track in a generated playlist, and the thing the reason panel follows.
 *
 * Ports `.playlist-track` (`frontend/app.js:1624`): a `role="option"` in the
 * list's listbox, selected by click or by Enter and Space. The remove button
 * sits inside it, so its click must not also select the row.
 *
 * `TODO(phase-4)`: the mobile bottom sheet, which the legacy opens instead of
 * selecting below 768px.
 */
import type { Track } from '../../../api/generated/types.gen.ts'
import { AlbumArt } from '../../atoms/AlbumArt/AlbumArt.tsx'
import styles from './TrackRow.module.scss'

export interface TrackRowProps {
  readonly track: Track
  /** Its place in the playlist, one-based, as the reader counts. */
  readonly position: number
  readonly selected: boolean
  readonly onChoose: () => void
  readonly onRemove: () => void
}

export function TrackRow({
  track,
  position,
  selected,
  onChoose,
  onRemove,
}: TrackRowProps) {
  return (
    <div
      className={styles.trackRow}
      role="option"
      tabIndex={0}
      aria-selected={selected}
      aria-label={`${track.title} by ${track.artist}`}
      onClick={onChoose}
      onKeyDown={(event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return
        event.preventDefault()
        onChoose()
      }}
    >
      <span className={styles.trackRow__number}>{position}</span>
      <AlbumArt src={track.art_url} artist={track.artist} album={track.album} />
      <div className={styles.trackRow__info}>
        <div className={styles.trackRow__title}>{track.title}</div>
        <div className={styles.trackRow__artist}>
          {track.artist} - {track.album}
        </div>
      </div>
      <button
        type="button"
        className={styles.trackRow__remove}
        aria-label={`Remove ${track.title}`}
        onClick={(event) => {
          // Otherwise removing a row also selects it on the way out.
          event.stopPropagation()
          onRemove()
        }}
      >
        ×
      </button>
    </div>
  )
}
