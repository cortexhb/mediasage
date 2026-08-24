/**
 * A round's albums: the one being recommended, and the picks beside it.
 *
 * The live results step and a saved result draw the same thing from the same
 * shape (`frontend/app.js:604` rendered both into the same DOM), and differ
 * only in what may still be done with it: a live round can be replaced, a
 * saved one cannot. Those buttons are the caller's `children`.
 *
 * The save form posts to whichever route drew this, which is why the `intent`
 * it carries is a prop: the two actions name their branches differently.
 */
import type { ReactNode } from 'react'
import { Form } from 'react-router'

import type { AlbumRecommendation } from '../../../api/generated/types.gen.ts'
import { Button } from '../../atoms/Button/Button.tsx'
import { AlbumCard } from '../../molecules/AlbumCard/AlbumCard.tsx'
import { AlbumPitch } from '../AlbumPitch/AlbumPitch.tsx'
import { PlayNow } from '../PlayNow/PlayNow.tsx'
import styles from './AlbumResultView.module.scss'

export interface AlbumResultViewProps {
  readonly albums: readonly AlbumRecommendation[]
  /** What the research could not confirm, where the round said so. */
  readonly warning?: string | null | undefined
  /** The `intent` the save form carries, which the route's action reads. */
  readonly intent: string
  /** Actions beside Save on the primary pitch: another, start over. */
  readonly children?: ReactNode
}

export function AlbumResultView({
  albums,
  warning,
  intent,
  children,
}: AlbumResultViewProps) {
  const primary = albums.find((album) => album.rank === 'primary')
  const secondaries = albums.filter((album) => album.rank === 'secondary')

  /** The hidden fields one album's save needs. */
  const saving = (album: AlbumRecommendation) => (
    <>
      <input type="hidden" name="intent" value={intent} />
      <input type="hidden" name="album" value={album.album} />
      <input type="hidden" name="artist" value={album.artist} />
      <input type="hidden" name="pitch" value={album.pitch?.full_text ?? ''} />
      {(album.track_rating_keys ?? []).map((key) => (
        <input key={key} type="hidden" name="rating_keys" value={key} />
      ))}
    </>
  )

  return (
    <>
      {warning && <p className={styles.albumResultView__warning}>{warning}</p>}

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
          {children}
        </AlbumPitch>
      )}

      {secondaries.length > 0 && (
        <section className={styles.albumResultView__more}>
          <h3 className={styles.albumResultView__moreHeading}>
            Also worth exploring
          </h3>
          <div className={styles.albumResultView__cards}>
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
    </>
  )
}
