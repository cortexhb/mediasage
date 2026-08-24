/**
 * Why the chosen track is in the playlist.
 *
 * Ports `.track-reason-panel` and `showTrackReason` (`frontend/app.js:1529`).
 * A track with no reason of its own still gets a line, because an empty panel
 * reads as a broken one.
 *
 * Hidden below the mobile breakpoint, as the legacy stylesheet hides it: the
 * bottom sheet that replaced it there is `TODO(phase-4)`.
 */
import type { Track } from '../../../api/generated/types.gen.ts'
import { AlbumArt } from '../../atoms/AlbumArt/AlbumArt.tsx'
import styles from './TrackReasonPanel.module.scss'

const PLACEHOLDER = 'Click a track to see why it was chosen'

/** `frontend/app.js:1548`, for a track the model returned without one. */
const UNEXPLAINED = 'Selected for this playlist'

export interface TrackReasonPanelProps {
  /** Nothing chosen yet, which is what the placeholder is for. */
  readonly track?: Track | undefined
  readonly reason?: string | undefined
}

export function TrackReasonPanel({ track, reason }: TrackReasonPanelProps) {
  return (
    <aside className={styles.trackReasonPanel}>
      {track ? (
        <div className={styles.trackReasonPanel__content}>
          <div className={styles.trackReasonPanel__art}>
            <AlbumArt
              src={track.art_url}
              artist={track.artist}
              album={track.album}
              size="large"
            />
          </div>
          <div className={styles.trackReasonPanel__title}>{track.title}</div>
          <div className={styles.trackReasonPanel__artist}>
            {track.artist} - {track.album}
          </div>
          <p className={styles.trackReasonPanel__reason}>
            {reason?.trim() ? reason : UNEXPLAINED}
          </p>
        </div>
      ) : (
        <div className={styles.trackReasonPanel__placeholder}>
          {PLACEHOLDER}
        </div>
      )}
    </aside>
  )
}
