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
 * The version and model on the left come from `GET /api/config` through a
 * fetcher, not a loader: every navigation would otherwise wait on a read that
 * fills one line of text. `libs/loadFooter` holds it.
 */
import { useEffect, useRef, useState } from 'react'
import { useFetcher, useLocation } from 'react-router'

import { Button } from '../../atoms/Button/Button.tsx'
import { Overlay } from '../../atoms/Overlay/Overlay.tsx'
import { ProgressBar } from '../../atoms/ProgressBar/ProgressBar.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import { readPlaylistFlow } from '../../../libs/flowStore/flowStore.ts'
import { generateBody } from '../../../libs/generateBody/generateBody.ts'
import type { FooterFacts } from '../../../libs/loadFooter/loadFooter.ts'
import { forgetRun, startRun } from '../../../libs/playlistRun/playlistRun.ts'
import { streamDeadline } from '../../../libs/streamDeadline/streamDeadline.ts'
import { syncProgress } from '../../../libs/syncProgress/syncProgress.ts'
import { timeAgo } from '../../../libs/timeAgo/timeAgo.ts'
import { useGeneratedPlaylist } from '../../../libs/useGeneratedPlaylist/useGeneratedPlaylist.ts'
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

/** What a finished run cost, as `frontend/app.js:1701` worded it. */
function spent(tokens: number, cost: number, local: boolean): string {
  const counted = `${tokens.toLocaleString()} tokens`
  return local ? counted : `${counted} ($${cost.toFixed(4)})`
}

/**
 * Generate the same request again, with the filters it already carries.
 *
 * A click, and the only other place a generation begins: the flow record has
 * everything the request needs, so nothing about the page is involved.
 */
function regenerate(): void {
  const flow = readPlaylistFlow()
  if (!flow?.filters) return
  const body = generateBody(
    flow.id,
    flow.prompt,
    flow.refinementAnswers,
    flow.filters,
  )

  forgetRun()
  const aborter = new AbortController()
  streamDeadline(aborter.signal)
    .then((deadline) => {
      startRun(body, deadline)
    })
    .catch(() => undefined)
}

export function Footer() {
  const sync = useSharedLibrarySync()
  const facts = useFetcher<FooterFacts | null>()
  const run = useGeneratedPlaylist()
  // `.footer-results-only`: the totals belong to the page that produced them.
  const onResults = useLocation().pathname === '/playlist/prompt/playlist'
  const [open, setOpen] = useState(false)
  const status = sync.status
  const running = status?.is_syncing ?? false
  const report = syncProgress(status?.sync_progress ?? null)

  // The last poll, so the effect sees edges rather than levels.
  const before = useRef({ running: false, blocking: false })

  useEffect(() => {
    // Once: the version cannot change under a running page.
    if (facts.state === 'idle' && !facts.data) {
      Promise.resolve(facts.load('/footer')).catch(() => undefined)
    }
  }, [facts])

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
      <div className={styles.footer__identity}>
        <a
          className={styles.footer__brand}
          href="https://github.com/ecwilsonaz/mediasage"
          target="_blank"
          rel="noopener"
        >
          MediaSage {facts.data && `v${facts.data.version}`}
        </a>
        {facts.data && (
          <>
            <span className={styles.footer__separator}>·</span>
            {/* Titled because a long model name is truncated. */}
            <span className={styles.footer__model} title={facts.data.model}>
              {facts.data.model}
            </span>
          </>
        )}
      </div>

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
          {/* Not a `Button`: `.footer-refresh` is accent-coloured. */}
          <button
            type="button"
            className={styles.footer__refresh}
            onClick={sync.start}
            disabled={running}
          >
            {sync.unsynced ? 'Sync now' : 'Refresh'}
          </button>
        </div>
      )}

      {onResults && (
        <button
          type="button"
          className={styles.footer__regenerate}
          disabled={run.running}
          onClick={() => {
            regenerate()
          }}
        >
          ↻ Regenerate Playlist
        </button>
      )}

      {onResults && run.totals && (
        <span className={styles.footer__cost}>
          {spent(
            run.totals.token_count,
            run.totals.estimated_cost,
            facts.data?.local ?? false,
          )}
        </span>
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
