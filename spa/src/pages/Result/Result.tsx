/**
 * One saved result, read back from history.
 *
 * Both flows end here, which is why the route is `/result/:resultId` rather
 * than one address per kind: `frontend/app.js:3138` and `:4503` already
 * rewrote the hash to that shape once a result was stored.
 *
 * Read-only. `frontend/app.js:604` rehydrated the live wizard instead, so a
 * saved playlist arrived offering Regenerate and a saved album offering Show
 * Me Another -- both backed by a session that no longer existed. What is kept
 * is what a snapshot can honestly still do: play it, and save it to Plex.
 *
 * The two layouts are the live steps' own components, because in legacy they
 * were the same DOM: `organisms/AlbumResultView` and
 * `organisms/PlaylistResultGrid`, each drawn without the buttons a live
 * session would add.
 */
import { useState } from 'react'
import { useActionData, useLoaderData } from 'react-router'

import type { ResultDetail } from '../../api/results/results.ts'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { AlbumResultView } from '../../components/organisms/AlbumResultView/AlbumResultView.tsx'
import { PlaylistResultGrid } from '../../components/organisms/PlaylistResultGrid/PlaylistResultGrid.tsx'
import { PlaylistSavedDialog } from '../../components/organisms/PlaylistSavedDialog/PlaylistSavedDialog.tsx'
import { PlaylistUpdatedDialog } from '../../components/organisms/PlaylistUpdatedDialog/PlaylistUpdatedDialog.tsx'
import type { SaveMode } from '../../components/organisms/SavePlaylist/SavePlaylist.tsx'
import type { SaveResult } from '../../libs/savePlaylistToPlex/savePlaylistToPlex.ts'
import type { ResultSaveAction } from '../../libs/saveResultToPlex/saveResultToPlex.ts'
import { useGo } from '../../libs/useGo/useGo.ts'
import styles from './Result.module.scss'

export function Result() {
  const detail = useLoaderData<ResultDetail>()
  const action = useActionData<ResultSaveAction>()
  const go = useGo()
  const [mode, setMode] = useState<SaveMode>('new')
  const [name, setName] = useState<string | null>(null)

  // Re-navigating is what clears the action's result, and the dialog with it.
  const dismiss = (): void => {
    go('.')
  }

  /** Where a fresh one begins: the flow that produced this result. */
  const afresh = (): void => {
    go(detail.type === 'seed_playlist' ? '/playlist/seed' : '/playlist/prompt')
  }

  const failure = action?.error
  // A string means the album save. The playlist one answers a dialog.
  const announced = typeof action?.saved === 'string' ? action.saved : ''
  const saved = (action as SaveResult | undefined)?.saved

  if (detail.type === 'album_recommendation') {
    return (
      <div className={styles.result__album}>
        {failure && (
          <Text tone="error" role="alert">
            {failure}
          </Text>
        )}
        {announced && (
          <Text tone="success" role="status">
            {announced}
          </Text>
        )}

        <AlbumResultView
          albums={detail.snapshot.recommendations}
          warning={detail.snapshot.research_warning}
          intent="album"
        />
      </div>
    )
  }

  const snapshot = detail.snapshot
  // Not `??`: an empty snapshot title falls back too.
  const title =
    name ??
    (snapshot.playlist_title?.length ? snapshot.playlist_title : detail.title)

  return (
    <div>
      {failure && (
        <Text tone="error" role="alert">
          {failure}
        </Text>
      )}

      <PlaylistResultGrid
        name={title}
        onName={setName}
        narrative={snapshot.narrative ?? ''}
        prompt={detail.type === 'prompt_playlist' ? detail.prompt : undefined}
        tracks={snapshot.tracks}
        reasons={snapshot.track_reasons ?? undefined}
        label="Saved playlist"
        mode={mode}
        onMode={setMode}
      />

      <PlaylistSavedDialog
        open={Boolean(saved && !saved.updated)}
        summary={saved?.summary ?? ''}
        url={saved?.url}
        onDismiss={dismiss}
        onNewPlaylist={afresh}
      />

      <PlaylistUpdatedDialog
        open={Boolean(saved?.updated)}
        summary={saved?.summary ?? ''}
        url={saved?.url}
        onDismiss={dismiss}
        onNewPlaylist={afresh}
      />
    </div>
  )
}
