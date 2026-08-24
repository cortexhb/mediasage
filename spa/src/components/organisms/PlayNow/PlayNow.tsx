/**
 * Sending the playlist to a Plex device instead of saving it.
 *
 * Ports the client picker (`frontend/index.html:784`, `frontend/app.js:3391`).
 * The device list is read when the dialog opens, never before: it reflects
 * what is awake right now, so a list read on page load would be stale.
 *
 * The dots are the legend the legacy modal carries: a mobile player takes a
 * queue only while something is already playing on it.
 *
 * `TODO(phase-4)`: the play-choice dialog that offers "play next" as well as
 * replacing the queue (`frontend/style.css:2295`); this always replaces.
 */
import { useEffect, useState } from 'react'

import type { PlexClientInfo } from '../../../api/generated/types.gen.ts'
import {
  createPlayQueue,
  listPlexClients,
} from '../../../api/playback/playback.ts'
import { explainError } from '../../../libs/explainError/explainError.ts'
import { Button } from '../../atoms/Button/Button.tsx'
import { Overlay } from '../../atoms/Overlay/Overlay.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import styles from './PlayNow.module.scss'

const EMPTY = 'No Plex clients active. Open Plexamp or Plex first.'

/** The three states a device can be in, worded as `frontend/app.js:3381`. */
function status(client: PlexClientInfo): { state: string; text: string } {
  if (client.is_playing) return { state: 'playing', text: 'Playing' }
  if (client.is_mobile)
    return { state: 'mobile', text: 'Idle — start playing on device first' }
  return { state: 'idle', text: 'Idle — may be slow to respond' }
}

export interface PlayNowProps {
  readonly ratingKeys: readonly string[]
  /**
   * How the trigger is drawn. Defaults to the playlist step's own.
   *
   * The album flow draws three of these on one screen: a primary one under
   * the pitch and a small secondary one on each card
   * (`frontend/app.js:4700`, `:4728`).
   */
  readonly variant?: 'primary' | 'secondary'
  readonly size?: 'sm'
  readonly label?: string
}

export function PlayNow({
  ratingKeys,
  variant = 'secondary',
  size,
  label = '▶ Play Now',
}: PlayNowProps) {
  const [open, setOpen] = useState(false)
  const [clients, setClients] = useState<PlexClientInfo[] | null>(null)
  const [failure, setFailure] = useState('')

  useEffect(() => {
    if (!open) return
    const aborter = new AbortController()
    listPlexClients(aborter.signal)
      .then(setClients)
      .catch((error: unknown) => {
        if (aborter.signal.aborted) return
        setClients([])
        setFailure(explainError(error))
      })
    return () => {
      aborter.abort()
    }
  }, [open])

  const play = (clientId: string): void => {
    createPlayQueue(
      { rating_keys: [...ratingKeys], client_id: clientId, mode: 'replace' },
      new AbortController().signal,
    )
      .then((result) => {
        if (result.success) setOpen(false)
        else setFailure(result.error ?? 'Could not start playback')
      })
      .catch((error: unknown) => {
        setFailure(explainError(error))
      })
  }

  return (
    <>
      <Button
        variant={variant}
        size={size}
        disabled={!ratingKeys.length}
        onClick={() => {
          setFailure('')
          // Cleared here, not in the effect: opening re-reads the list.
          setClients(null)
          setOpen(true)
        }}
      >
        {label}
      </Button>

      <Overlay
        open={open}
        onClose={() => {
          setOpen(false)
        }}
        label="Select a Device"
      >
        <div className={styles.playNow}>
          <h2>Select a Device</h2>
          {clients?.length ? (
            <p className={styles.playNow__legend}>
              <span className={styles.playNow__hint}>
                <span className={styles.playNow__dot} data-state="playing" />{' '}
                Playing
              </span>
              <span className={styles.playNow__hint}>
                <span className={styles.playNow__dot} data-state="idle" /> Idle
              </span>
              <span className={styles.playNow__hint}>
                <span className={styles.playNow__dot} data-state="mobile" />{' '}
                Needs active session
              </span>
            </p>
          ) : null}

          {clients === null && (
            <Text tone="secondary">Looking for devices…</Text>
          )}

          {clients?.length === 0 && (
            <div className={styles.playNow__empty}>
              <Text tone="secondary">{EMPTY}</Text>
            </div>
          )}

          {clients && clients.length > 0 && (
            <div
              className={styles.playNow__list}
              role="listbox"
              aria-label="Available devices"
            >
              {clients.map((client) => (
                <button
                  key={client.client_id}
                  type="button"
                  role="option"
                  aria-selected="false"
                  className={styles.playNow__client}
                  onClick={() => {
                    play(client.client_id)
                  }}
                >
                  <span
                    className={styles.playNow__dot}
                    data-state={status(client).state}
                    aria-hidden="true"
                  />
                  <span className={styles.playNow__info}>
                    <span className={styles.playNow__name}>{client.name}</span>
                    <span className={styles.playNow__product}>
                      {client.product}
                    </span>{' '}
                    <span className={styles.playNow__platform}>
                      {client.platform}
                    </span>
                    <span
                      className={styles.playNow__status}
                      data-state={status(client).state}
                    >
                      {status(client).text}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}

          {failure && (
            <Text tone="error" role="alert">
              {failure}
            </Text>
          )}
        </div>
      </Overlay>
    </>
  )
}
