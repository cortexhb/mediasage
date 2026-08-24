/**
 * The dialog after a new playlist is written to Plex.
 *
 * Ports `#success-modal` (`frontend/index.html:482`): the green disc, the
 * sentence, and three stacked actions. "Start New Playlist" is
 * `resetPlaylistState` (`frontend/app.js:2183`); "Back to Playlist" only
 * dismisses.
 *
 * Replace and append get `PlaylistUpdatedDialog` instead -- a different modal
 * in legacy, not a variant of this one.
 */
import { Button } from '../../atoms/Button/Button.tsx'
import { Overlay } from '../../atoms/Overlay/Overlay.tsx'
import { OpenInPlex } from '../../molecules/OpenInPlex/OpenInPlex.tsx'
import styles from './PlaylistSavedDialog.module.scss'

export interface PlaylistSavedDialogProps {
  readonly open: boolean
  /** The sentence, composed where the save happened. */
  readonly summary: string
  readonly url?: string | null | undefined
  readonly onDismiss: () => void
  readonly onNewPlaylist: () => void
}

export function PlaylistSavedDialog({
  open,
  summary,
  url,
  onDismiss,
  onNewPlaylist,
}: PlaylistSavedDialogProps) {
  return (
    <Overlay
      open={open}
      onClose={onDismiss}
      label="Playlist Saved!"
      size="compact"
    >
      <div className={styles.playlistSavedDialog}>
        <div className={styles.playlistSavedDialog__icon} aria-hidden="true" />
        <h2 className={styles.playlistSavedDialog__title}>Playlist Saved!</h2>
        <p className={styles.playlistSavedDialog__summary}>{summary}</p>
        <div className={styles.playlistSavedDialog__actions}>
          <OpenInPlex url={url} />
          <Button variant="primary" onClick={onNewPlaylist}>
            Start New Playlist
          </Button>
          <Button variant="secondary" onClick={onDismiss}>
            Back to Playlist
          </Button>
        </div>
      </div>
    </Overlay>
  )
}
