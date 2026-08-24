/**
 * Step four of the album flow: the album, and the case for it.
 *
 * **Nothing here starts a round.** The filters submit does, and so do the two
 * buttons that post to this route's action; this page only reads
 * `libs/albumRun`. A reload restores the round kept in the record instead of
 * buying another.
 *
 * The stages in the overlay are the ones the stream reports, not timed ones --
 * `progress` frames arrive as each call starts.
 *
 * The albums themselves are `organisms/AlbumResultView`, which a saved result
 * draws too; what is here is what only a live round can offer.
 *
 * No stepper: `frontend/app.js:1064` hides the progress bar on this step.
 */
import { useEffect } from 'react'
import { Form, useActionData, useLoaderData } from 'react-router'

import { Text } from '../../components/atoms/Text/Text.tsx'
import { WorkingOverlay } from '../../components/molecules/WorkingOverlay/WorkingOverlay.tsx'
import { AlbumResultView } from '../../components/organisms/AlbumResultView/AlbumResultView.tsx'
import type { AlbumResultAction } from '../../libs/actOnRecommendation/actOnRecommendation.ts'
import {
  forgetRound,
  restoreRound,
  ROUND_STEPS,
  useRecommendation,
} from '../../libs/albumRun/albumRun.ts'
import type { AlbumFlow } from '../../libs/albumStore/albumStore.ts'
import { forgetAlbumFlow } from '../../libs/albumStore/albumStore.ts'
import { forgetSuggestion } from '../../libs/suggestionCache/suggestionCache.ts'
import { useGo } from '../../libs/useGo/useGo.ts'
import styles from './AlbumResults.module.scss'

export function AlbumResults() {
  const flow = useLoaderData<AlbumFlow>()
  const round = useRecommendation()
  const result = useActionData<AlbumResultAction>()
  const go = useGo()

  useEffect(() => {
    // Redraws a finished round after a reload. Never buys one.
    if (flow.result) restoreRound(flow.result)
  }, [flow])

  /** `frontend/app.js:4957`: the flow is dropped and step one begins again. */
  const startOver = (): void => {
    forgetRound()
    forgetSuggestion()
    forgetAlbumFlow()
    go('/recommend')
  }

  const albums = round.result?.recommendations ?? []
  const primary = albums.find((album) => album.rank === 'primary')

  return (
    <div className={styles.albumResults}>
      {round.failure && (
        <Text tone="error" role="alert">
          {round.failure}
        </Text>
      )}
      {result?.error && (
        <Text tone="error" role="alert">
          {result.error}
        </Text>
      )}
      {result?.saved && (
        <Text tone="success" role="status">
          {result.saved}
        </Text>
      )}

      <AlbumResultView
        albums={albums}
        warning={round.result?.research_warning}
        intent="save"
      >
        <Form method="post">
          <input type="hidden" name="intent" value="again" />
          <button type="submit" className={styles.albumResults__link}>
            Show Me Another
          </button>
        </Form>
        <button
          type="button"
          className={styles.albumResults__link}
          data-tone="subtle"
          onClick={startOver}
        >
          Start over
        </button>
      </AlbumResultView>

      {/* Library mode only: there is nothing to bridge to from discovery. */}
      {flow.mode === 'library' && primary && (
        <Form method="post" className={styles.albumResults__bridge}>
          <input type="hidden" name="intent" value="discovery" />
          <button type="submit" className={styles.albumResults__discovery}>
            Recommend something not in my library
          </button>
        </Form>
      )}

      <WorkingOverlay
        open={round.running}
        label="Finding an album"
        steps={ROUND_STEPS}
        at={round.stage}
      />
    </div>
  )
}
