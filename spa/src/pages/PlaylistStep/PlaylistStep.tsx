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
 * The grid itself is `organisms/PlaylistResultGrid`, which a saved result
 * draws too; what is here is the live run around it.
 */
import { useEffect, useState } from 'react'
import { useActionData, useLoaderData } from 'react-router'

import { Text } from '../../components/atoms/Text/Text.tsx'
import { WorkingOverlay } from '../../components/molecules/WorkingOverlay/WorkingOverlay.tsx'
import { PlaylistResultGrid } from '../../components/organisms/PlaylistResultGrid/PlaylistResultGrid.tsx'
import { PlaylistSavedDialog } from '../../components/organisms/PlaylistSavedDialog/PlaylistSavedDialog.tsx'
import { PlaylistUpdatedDialog } from '../../components/organisms/PlaylistUpdatedDialog/PlaylistUpdatedDialog.tsx'
import type { SaveMode } from '../../components/organisms/SavePlaylist/SavePlaylist.tsx'
import type { PlaylistFlow } from '../../libs/flowStore/flowStore.ts'
import { forgetPlaylistFlow } from '../../libs/flowStore/flowStore.ts'
import { playlistName } from '../../libs/playlistName/playlistName.ts'
import {
  forgetRun,
  GENERATION_STEPS,
  restoreRun,
  useGeneratedPlaylist,
} from '../../libs/playlistRun/playlistRun.ts'
import type { SaveResult } from '../../libs/savePlaylistToPlex/savePlaylistToPlex.ts'
import { useGo } from '../../libs/useGo/useGo.ts'
import styles from './PlaylistStep.module.scss'

export function PlaylistStep() {
  const flow = useLoaderData<PlaylistFlow>()
  const run = useGeneratedPlaylist()
  const result = useActionData<SaveResult>()
  const go = useGo()

  // Null until typed: the model's title is the offer until then.
  const [typed, setTyped] = useState<string | null>(null)
  const [dropped, setDropped] = useState<readonly string[]>([])
  const [mode, setMode] = useState<SaveMode>('new')

  useEffect(() => {
    // Redraws a finished run after a reload. Never buys one.
    if (flow.playlist) restoreRun(flow.playlist)
  }, [flow])

  // Back to the playlist: re-navigating is what clears the action's result.
  const dismiss = (): void => {
    go('.')
  }

  /** `frontend/app.js:2183`: the flow is dropped and step one begins again. */
  const startOver = (): void => {
    forgetRun()
    forgetPlaylistFlow()
    go(`/playlist/${flow.mode}`)
  }

  const tracks = run.tracks.filter(
    (track) => !dropped.includes(track.rating_key),
  )
  const name = typed ?? (run.title || playlistName(flow, new Date()))

  return (
    <div>
      {/* No stepper: `frontend/app.js:1053` hides it on the results step. */}
      <button
        type="button"
        className={styles.playlist__back}
        onClick={() => {
          go(`/playlist/${flow.mode}/filters`)
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

      <PlaylistResultGrid
        name={name}
        onName={setTyped}
        narrative={run.narrative}
        prompt={flow.mode === 'prompt' ? flow.prompt : undefined}
        tracks={tracks}
        reasons={run.reasons}
        label="Generated playlist"
        mode={mode}
        onMode={setMode}
        onRemove={(ratingKey) => {
          setDropped([...dropped, ratingKey])
        }}
      >
        <button
          type="button"
          className={styles.playlist__startOver}
          onClick={startOver}
        >
          Start over
        </button>
      </PlaylistResultGrid>

      <WorkingOverlay
        open={run.running}
        label="Generating your playlist"
        steps={GENERATION_STEPS}
        at={run.stage}
      />

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
