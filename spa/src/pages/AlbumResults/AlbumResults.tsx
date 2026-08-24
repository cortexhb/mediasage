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
 * No stepper: `frontend/app.js:1064` hides the progress bar on this step.
 */
import { useEffect, useState } from 'react'
import { Form, useActionData, useLoaderData, useNavigate } from 'react-router'

import type { AlbumRecommendation } from '../../api/generated/types.gen.ts'
import { Button } from '../../components/atoms/Button/Button.tsx'
import { Overlay } from '../../components/atoms/Overlay/Overlay.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { AlbumCard } from '../../components/molecules/AlbumCard/AlbumCard.tsx'
import { StepProgress } from '../../components/molecules/StepProgress/StepProgress.tsx'
import { AlbumPitch } from '../../components/organisms/AlbumPitch/AlbumPitch.tsx'
import { PlayNow } from '../../components/organisms/PlayNow/PlayNow.tsx'
import type { AlbumResultAction } from '../../libs/actOnRecommendation/actOnRecommendation.ts'
import {
  forgetRound,
  restoreRound,
  ROUND_STEPS,
} from '../../libs/albumRun/albumRun.ts'
import type { AlbumFlow } from '../../libs/albumStore/albumStore.ts'
import { forgetAlbumFlow } from '../../libs/albumStore/albumStore.ts'
import { forgetSuggestion } from '../../libs/suggestionCache/suggestionCache.ts'
import { useRecommendation } from '../../libs/useRecommendation/useRecommendation.ts'
import styles from './AlbumResults.module.scss'

export function AlbumResults() {
  const flow = useLoaderData<AlbumFlow>()
  const round = useRecommendation()
  const result = useActionData<AlbumResultAction>()
  const navigate = useNavigate()
  const [watching, setWatching] = useState(true)

  useEffect(() => {
    // Redraws a finished round after a reload. Never buys one.
    if (flow.result) restoreRound(flow.result)
  }, [flow])

  /** `frontend/app.js:4957`: the flow is dropped and step one begins again. */
  const startOver = (): void => {
    forgetRound()
    forgetSuggestion()
    forgetAlbumFlow()
    Promise.resolve(navigate('/recommend')).catch(() => undefined)
  }

  const albums = round.result?.recommendations ?? []
  const primary = albums.find((album) => album.rank === 'primary')
  const secondaries = albums.filter((album) => album.rank === 'secondary')

  /** The hidden fields one album's save needs. */
  const saving = (album: AlbumRecommendation) => (
    <>
      <input type="hidden" name="intent" value="save" />
      <input type="hidden" name="album" value={album.album} />
      <input type="hidden" name="artist" value={album.artist} />
      <input type="hidden" name="pitch" value={album.pitch?.full_text ?? ''} />
      {(album.track_rating_keys ?? []).map((key) => (
        <input key={key} type="hidden" name="rating_keys" value={key} />
      ))}
    </>
  )

  return (
    <div className={styles.albumResults}>
      {round.result?.research_warning && (
        <p className={styles.albumResults__warning}>
          {round.result.research_warning}
        </p>
      )}

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

      {primary && (
        <AlbumPitch album={primary}>
          {primary.track_rating_keys?.length ? (
            <>
              <PlayNow
                ratingKeys={primary.track_rating_keys}
                variant="primary"
              />
              <Form method="post">
                {saving(primary)}
                <Button type="submit" variant="secondary">
                  Save to Playlist
                </Button>
              </Form>
            </>
          ) : null}
          <Form
            method="post"
            onSubmit={() => {
              // Dismissed once, shown again for the next round.
              setWatching(true)
            }}
          >
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
        </AlbumPitch>
      )}

      {secondaries.length > 0 && (
        <section className={styles.albumResults__more}>
          <h3 className={styles.albumResults__moreHeading}>
            Also worth exploring
          </h3>
          <div className={styles.albumResults__cards}>
            {secondaries.map((album) => (
              <AlbumCard key={`${album.artist}-${album.album}`} album={album}>
                {album.track_rating_keys?.length ? (
                  <>
                    <PlayNow
                      ratingKeys={album.track_rating_keys}
                      size="sm"
                      label="▶ Play"
                    />
                    <Form method="post">
                      {saving(album)}
                      <Button type="submit" variant="secondary" size="sm">
                        Save
                      </Button>
                    </Form>
                  </>
                ) : null}
              </AlbumCard>
            ))}
          </div>
        </section>
      )}

      {/* Library mode only: there is nothing to bridge to from discovery. */}
      {flow.mode === 'library' && primary && (
        <Form
          method="post"
          className={styles.albumResults__bridge}
          onSubmit={() => {
            setWatching(true)
          }}
        >
          <input type="hidden" name="intent" value="discovery" />
          <button type="submit" className={styles.albumResults__discovery}>
            Recommend something not in my library
          </button>
        </Form>
      )}

      {/* Dismissable: closing it abandons the wait, not the round. */}
      <Overlay
        open={round.running && watching}
        onClose={() => {
          setWatching(false)
        }}
        label="Finding an album"
      >
        <div className={styles.albumResults__working}>
          <StepProgress steps={ROUND_STEPS} at={round.stage} />
        </div>
      </Overlay>
    </div>
  )
}
