/**
 * The dialog after tracks are written into a playlist that already existed.
 *
 * Ports `#update-success-modal` (`frontend/index.html:497`): the drawn ring,
 * "Playlist Updated", and two actions side by side. Replace and append share
 * it; only the sentence differs, and that is composed at the save.
 */
import { Button } from '../../atoms/Button/Button.tsx'
import { Overlay } from '../../atoms/Overlay/Overlay.tsx'
import { OpenInPlex } from '../../molecules/OpenInPlex/OpenInPlex.tsx'
import styles from './PlaylistUpdatedDialog.module.scss'

export interface PlaylistUpdatedDialogProps {
  readonly open: boolean
  readonly summary: string
  readonly url?: string | null | undefined
  readonly onDismiss: () => void
  readonly onNewPlaylist: () => void
}

export function PlaylistUpdatedDialog({
  open,
  summary,
  url,
  onDismiss,
  onNewPlaylist,
}: PlaylistUpdatedDialogProps) {
  return (
    <Overlay
      open={open}
      onClose={onDismiss}
      label="Playlist Updated"
      size="compact"
    >
      <>
        <div className={styles.playlistUpdatedDialog__hero}>
          <div className={styles.playlistUpdatedDialog__ring}>
            <svg
              className={styles.playlistUpdatedDialog__ringSvg}
              viewBox="0 0 48 48"
              fill="none"
              aria-hidden="true"
            >
              <circle
                className={styles.playlistUpdatedDialog__ringTrack}
                cx="24"
                cy="24"
                r="22"
                strokeWidth="3"
              />
              <circle
                className={styles.playlistUpdatedDialog__ringDrawn}
                cx="24"
                cy="24"
                r="22"
                strokeWidth="3"
              />
            </svg>
            <div
              className={styles.playlistUpdatedDialog__tick}
              aria-hidden="true"
            >
              ✓
            </div>
          </div>
          <h2 className={styles.playlistUpdatedDialog__title}>
            Playlist Updated
          </h2>
        </div>
        <div className={styles.playlistUpdatedDialog__details}>
          <p className={styles.playlistUpdatedDialog__line}>{summary}</p>
        </div>
        <div className={styles.playlistUpdatedDialog__actions}>
          <OpenInPlex url={url} />
          <Button variant="primary" onClick={onNewPlaylist}>
            New Playlist
          </Button>
        </div>
      </>
    </Overlay>
  )
}
