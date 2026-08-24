/**
 * One of the round's other picks, with its one-line pitch.
 *
 * Ports `.rec-secondary-card` (`frontend/app.js:4719`). A secondary pick is
 * written as `short_pitch`; `full_text` is the fallback the legacy used where
 * the writer filled only that.
 *
 * The actions are the caller's, for the reason `organisms/AlbumPitch` gives.
 */
import type { ReactNode } from 'react'

import type { AlbumRecommendation } from '../../../api/generated/types.gen.ts'
import { AlbumArt } from '../../atoms/AlbumArt/AlbumArt.tsx'
import styles from './AlbumCard.module.scss'

export interface AlbumCardProps {
  readonly album: AlbumRecommendation
  /** The play and save buttons, beside the title. */
  readonly children: ReactNode
}

export function AlbumCard({ album, children }: AlbumCardProps) {
  const pitch = album.pitch

  return (
    <div className={styles.albumCard}>
      <div className={styles.albumCard__header}>
        <AlbumArt
          src={album.art_url}
          artist={album.artist}
          album={album.album}
          size="card"
        />
        <div className={styles.albumCard__info}>
          <p className={styles.albumCard__title}>{album.album}</p>
          <p className={styles.albumCard__artist}>
            {album.artist}
            {album.year ? ` (${String(album.year)})` : ''}
          </p>
          <div className={styles.albumCard__actions}>{children}</div>
        </div>
      </div>
      <p className={styles.albumCard__pitch}>
        {pitch?.short_pitch?.length
          ? pitch.short_pitch
          : (pitch?.full_text ?? '')}
      </p>
    </div>
  )
}
