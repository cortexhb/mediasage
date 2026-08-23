/**
 * A labelled figure per line: total tracks, genres, decades.
 *
 * Split from `organisms/LibraryStats`, which owns waiting for the counts;
 * this owns showing them, and so renders with no async of its own.
 */
import type { LibraryStatsResponse } from '../../../api/generated/types.gen.ts'
import styles from './Counts.module.scss'

export interface CountsProps {
  readonly stats: LibraryStatsResponse
}

export function Counts({ stats }: CountsProps) {
  return (
    <dl className={styles.counts}>
      <dt className={styles.counts__term}>Total Tracks</dt>
      <dd className={styles.counts__value}>
        {stats.total_tracks.toLocaleString()}
      </dd>
      <dt className={styles.counts__term}>Genres</dt>
      <dd className={styles.counts__value}>
        {stats.genres.length.toLocaleString()}
      </dd>
      <dt className={styles.counts__term}>Decades</dt>
      <dd className={styles.counts__value}>
        {stats.decades.map((decade) => decade.name).join(', ') || 'None'}
      </dd>
    </dl>
  )
}
