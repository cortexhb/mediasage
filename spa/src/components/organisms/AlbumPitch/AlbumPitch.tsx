/**
 * The album the round is actually recommending, and the case for it.
 *
 * Ports `.rec-primary-result` (`frontend/app.js:4667`). The four parts of the
 * pitch are drawn only where the writer filled them: a secondary pick fills
 * none of them, and a rewrite can leave one empty
 * (`backend/recommender/prompts.py`, `REWRITE_SYSTEM`).
 *
 * The actions are the caller's, because they are a form and a dialog that
 * belong to the page: this draws the row they sit in.
 */
import type { ReactNode } from 'react'

import type { AlbumRecommendation } from '../../../api/generated/types.gen.ts'
import { AlbumArt } from '../../atoms/AlbumArt/AlbumArt.tsx'
import styles from './AlbumPitch.module.scss'

export interface AlbumPitchProps {
  readonly album: AlbumRecommendation
  /** The row under the pitch: play, save, another, start over. */
  readonly children: ReactNode
}

export function AlbumPitch({ album, children }: AlbumPitchProps) {
  const pitch = album.pitch

  return (
    <div className={styles.albumPitch}>
      <div className={styles.albumPitch__art}>
        <AlbumArt
          src={album.art_url}
          artist={album.artist}
          album={album.album}
          size="pitch"
        />
      </div>

      <div className={styles.albumPitch__body}>
        <h2 className={styles.albumPitch__album}>{album.album}</h2>
        <p className={styles.albumPitch__artist}>
          {album.artist}
          {album.year ? ` (${String(album.year)})` : ''}
        </p>

        {pitch?.hook && <p className={styles.albumPitch__hook}>{pitch.hook}</p>}

        {pitch?.context && (
          <section className={styles.albumPitch__section}>
            <h3 className={styles.albumPitch__label}>The Story</h3>
            {pitch.context}
          </section>
        )}

        {pitch?.listening_guide && (
          <section className={styles.albumPitch__section}>
            <h3 className={styles.albumPitch__label}>How to Listen</h3>
            {pitch.listening_guide}
          </section>
        )}

        {pitch?.connection && (
          <section
            className={styles.albumPitch__section}
            data-kind="connection"
          >
            <h3 className={styles.albumPitch__label}>Why This Album</h3>
            {pitch.connection}
          </section>
        )}

        <div className={styles.albumPitch__actions}>{children}</div>
      </div>
    </div>
  )
}
