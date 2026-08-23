/**
 * The status bar under every page: what the library holds, and a way to resync.
 *
 * It reads the shell's `LibrarySyncProvider`, so the poll runs once for the
 * whole app rather than once per component that cares.
 *
 * A first sync opens the `Overlay` on its own, because until it finishes there
 * is nothing to play from. `frontend/app.js:2372` made that modal inescapable
 * and, once hidden, unreachable — the sync then reported only in this bar.
 * Here the dialog is a view of the sync rather than a stage of it: dismissing
 * it never ends the sync, and the progress text reopens it at any point.
 *
 * `frontend/index.html:890` also showed the app version and the configured
 * model here. Both come from `GET /api/config`, which no route above this one
 * loads, and a loader on the shell would make every navigation wait on it.
 * They arrive when something else already needs that read.
 */
import { useEffect, useRef, useState } from 'react'

import { Button } from '../../atoms/Button/Button.tsx'
import { Overlay } from '../../atoms/Overlay/Overlay.tsx'
import { ProgressBar } from '../../atoms/ProgressBar/ProgressBar.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import { syncProgress } from '../../../libs/syncProgress/syncProgress.ts'
import { timeAgo } from '../../../libs/timeAgo/timeAgo.ts'
import { useSharedLibrarySync } from '../../../libs/useLibrarySync/useLibrarySync.ts'
import styles from './Footer.module.scss'

/** Said while the library is unusable, which is what a first sync means. */
const FIRST =
  'Reading your music from Plex. This runs once and takes a few minutes on a large library.'

/** Said while it is usable, so nothing here should read as a wait. */
const AGAIN =
  'Reading your music from Plex. The app stays usable while this runs.'

/**
 * The right-hand half of the bar: when it last synced, or how it is going.
 *
 * A percentage only while there is one to report. A phase with no denominator
 * would otherwise sit at "Syncing 0%" for minutes on a large library.
 */
function syncing(percent: number | null): string {
  return percent === null
    ? 'Syncing…'
    : `Syncing ${String(Math.round(percent))}%`
}

export function Footer() {
  const sync = useSharedLibrarySync()
  const [open, setOpen] = useState(false)
  const status = sync.status
  const running = status?.is_syncing ?? false
  const report = syncProgress(status?.sync_progress ?? null)

  // The last poll, so the effect sees edges rather than levels.
  const before = useRef({ running: false, blocking: false })

  useEffect(() => {
    const was = before.current
    before.current = { running, blocking: sync.blocking }

    // Opened for a first sync only. A resync is announced, not interrupted.
    if (sync.blocking && !was.blocking) setOpen(true)
    // Nothing left to show, and it would cover the page.
    if (!running && was.running) setOpen(false)
  }, [running, sync.blocking])

  // Silent before the first poll, and with no Plex behind it.
  const worth =
    status && (status.track_count > 0 || status.is_syncing || sync.unsynced)

  return (
    <footer className={styles.footer}>
      <a
        className={styles.footer__brand}
        href="https://github.com/ecwilsonaz/mediasage"
        target="_blank"
        rel="noopener"
      >
        MediaSage on GitHub
      </a>

      {worth && (
        <div className={styles.footer__library}>
          {sync.unsynced ? (
            <span>Library not synced</span>
          ) : (
            <>
              <span>{status.track_count.toLocaleString()} tracks</span>
              <span className={styles.footer__separator}>·</span>
              {running ? (
                <Button
                  variant="link"
                  onClick={() => {
                    setOpen(true)
                  }}
                >
                  {syncing(report.percent)}
                </Button>
              ) : (
                <span>{timeAgo(status.synced_at, new Date())}</span>
              )}
            </>
          )}
          <span className={styles.footer__separator}>·</span>
          <Button variant="link" onClick={sync.start} disabled={running}>
            {sync.unsynced ? 'Sync now' : 'Refresh'}
          </Button>
        </div>
      )}

      {sync.error && (
        <Text tone="error" role="alert">
          {sync.error}
        </Text>
      )}

      <Overlay
        open={open && running}
        onClose={() => {
          setOpen(false)
        }}
        label="Syncing your library"
      >
        <div className={styles.footer__sync}>
          <h2>Syncing your library</h2>
          <Text tone="secondary">{sync.blocking ? FIRST : AGAIN}</Text>
          <ProgressBar percent={report.percent} label="Library sync progress" />
          <Text tone="secondary">{report.text}</Text>
        </div>
      </Overlay>
    </footer>
  )
}
