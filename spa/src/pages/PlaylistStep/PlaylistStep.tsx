/**
 * Step four of the playlist flow: the playlist, as it streams in.
 *
 * **Nothing here starts a generation.** The filters submit does, and the
 * footer's Regenerate does; this page only reads `libs/playlistRun`. A reload
 * restores the playlist kept in the flow record instead of buying another.
 *
 * The stages in the overlay are the ones the stream reports, not timed ones --
 * `progress` frames arrive as each call starts (`frontend/app.js:3095`).
 *
 * The layout is the legacy results grid (`frontend/index.html:404`): the name
 * and narrative above the tracks, the actions and the reason panel beside
 * them. Selecting a track is what fills that panel, which is why the rows are
 * a listbox.
 */
import { useEffect, useState } from 'react'
import { Form, useActionData, useLoaderData, useNavigate } from 'react-router'

import { Overlay } from '../../components/atoms/Overlay/Overlay.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { StepProgress } from '../../components/molecules/StepProgress/StepProgress.tsx'
import { TrackRow } from '../../components/molecules/TrackRow/TrackRow.tsx'
import { PlayNow } from '../../components/organisms/PlayNow/PlayNow.tsx'
import { PlaylistPicker } from '../../components/organisms/PlaylistPicker/PlaylistPicker.tsx'
import { PlaylistSavedDialog } from '../../components/organisms/PlaylistSavedDialog/PlaylistSavedDialog.tsx'
import { PlaylistUpdatedDialog } from '../../components/organisms/PlaylistUpdatedDialog/PlaylistUpdatedDialog.tsx'
import type { SaveMode } from '../../components/organisms/SavePlaylist/SavePlaylist.tsx'
import { SavePlaylist } from '../../components/organisms/SavePlaylist/SavePlaylist.tsx'
import { TrackReasonPanel } from '../../components/organisms/TrackReasonPanel/TrackReasonPanel.tsx'
import type { PlaylistFlow } from '../../libs/flowStore/flowStore.ts'
import { forgetPlaylistFlow } from '../../libs/flowStore/flowStore.ts'
import { playlistName } from '../../libs/playlistName/playlistName.ts'
import {
  forgetRun,
  GENERATION_STEPS,
  restoreRun,
} from '../../libs/playlistRun/playlistRun.ts'
import type { SaveResult } from '../../libs/savePlaylistToPlex/savePlaylistToPlex.ts'
import { useGeneratedPlaylist } from '../../libs/useGeneratedPlaylist/useGeneratedPlaylist.ts'
import styles from './PlaylistStep.module.scss'

export function PlaylistStep() {
  const flow = useLoaderData<PlaylistFlow>()
  const run = useGeneratedPlaylist()
  const result = useActionData<SaveResult>()
  const navigate = useNavigate()

  // Null until typed: the model's title is the offer until then.
  const [typed, setTyped] = useState<string | null>(null)
  const [dropped, setDropped] = useState<readonly string[]>([])
  const [chosen, setChosen] = useState<string | null>(null)
  const [mode, setMode] = useState<SaveMode>('new')
  const [watching, setWatching] = useState(true)

  useEffect(() => {
    // Redraws a finished run after a reload. Never buys one.
    if (flow.playlist) restoreRun(flow.playlist)
  }, [flow])

  const go = (to: string): void => {
    Promise.resolve(navigate(to)).catch(() => undefined)
  }

  // Back to the playlist: re-navigating is what clears the action's result.
  const dismiss = (): void => {
    go('.')
  }

  /** `frontend/app.js:2183`: the flow is dropped and step one begins again. */
  const startOver = (): void => {
    forgetRun()
    forgetPlaylistFlow()
    go('/playlist/prompt')
  }

  const tracks = run.tracks.filter(
    (track) => !dropped.includes(track.rating_key),
  )
  // The first track until one is picked, as `frontend/app.js:1673` did it.
  const selected =
    tracks.find((track) => track.rating_key === chosen) ?? tracks[0]
  const name = typed ?? (run.title || playlistName(flow.prompt, new Date()))
  const count = `♫ ${String(tracks.length)} track${tracks.length === 1 ? '' : 's'}`

  return (
    <div>
      {/* No stepper: `frontend/app.js:1053` hides it on the results step. */}
      <button
        type="button"
        className={styles.playlist__back}
        onClick={() => {
          go('/playlist/prompt/filters')
        }}
      >
        ← Back to filters
      </button>

      {run.failure && (
        <Text tone="error" role="alert">
          {run.failure}
        </Text>
      )}
      {result?.error && (
        <Text tone="error" role="alert">
          {result.error}
        </Text>
      )}

      <Form method="post" className={styles.playlist__grid}>
        <div className={styles.playlist__header}>
          {/* Not an `Input`: this one is the page title as well as a field. */}
          {mode === 'new' ? (
            <input
              type="text"
              name="name"
              className={styles.playlist__name}
              value={name}
              onChange={(event) => {
                setTyped(event.target.value)
              }}
              placeholder="Enter playlist name..."
              aria-label="Playlist name"
            />
          ) : (
            <PlaylistPicker />
          )}
          {run.narrative && (
            <p className={styles.playlist__narrative}>{run.narrative}</p>
          )}
          <div className={styles.playlist__meta}>
            <span className={styles.playlist__pill}>{count}</span>
            {flow.prompt && (
              <span className={styles.playlist__prompt}>{flow.prompt}</span>
            )}
          </div>
        </div>

        <div className={styles.playlist__sidebar}>
          <div className={styles.playlist__actions}>
            <input type="hidden" name="description" value={run.narrative} />
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
              onMode={setMode}
              count={tracks.length}
              disabled={!tracks.length}
            />
            <PlayNow ratingKeys={tracks.map((track) => track.rating_key)} />
            <button
              type="button"
              className={styles.playlist__startOver}
              onClick={startOver}
            >
              Start over
            </button>
          </div>
          <TrackReasonPanel
            track={selected}
            reason={selected && run.reasons[selected.rating_key]}
          />
        </div>

        <div
          className={styles.playlist__tracks}
          role="listbox"
          aria-label="Generated playlist"
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
                setDropped([...dropped, track.rating_key])
              }}
            />
          ))}
        </div>
      </Form>

      {/* Dismissable: closing it abandons the wait, not the run. */}
      <Overlay
        open={run.running && watching}
        onClose={() => {
          setWatching(false)
        }}
        label="Generating your playlist"
      >
        <div className={styles.playlist__working}>
          <StepProgress steps={GENERATION_STEPS} at={run.stage} />
        </div>
      </Overlay>

      <PlaylistSavedDialog
        open={Boolean(result?.saved && !result.saved.updated)}
        summary={result?.saved?.summary ?? ''}
        url={result?.saved?.url}
        onDismiss={dismiss}
        onNewPlaylist={startOver}
      />

      <PlaylistUpdatedDialog
        open={Boolean(result?.saved?.updated)}
        summary={result?.saved?.summary ?? ''}
        url={result?.saved?.url}
        onDismiss={dismiss}
        onNewPlaylist={startOver}
      />
    </div>
  )
}
