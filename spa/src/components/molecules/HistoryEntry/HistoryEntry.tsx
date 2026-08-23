/**
 * One saved result in the feed.
 *
 * The title is the link and its `::after` covers the row, so the whole card is
 * clickable without nesting a delete button inside an anchor —
 * `frontend/app.js:945` solved the same problem with `stopPropagation` on a
 * div that no keyboard could reach.
 *
 * Deleting is two clicks. The confirming entry is decided by the feed, not
 * here, so opening one confirmation closes another.
 */
import { Link } from 'react-router'

import type { ResultListItem } from '../../../api/generated/types.gen.ts'
import { ModeIcon } from '../../atoms/ModeIcon/ModeIcon.tsx'
import { MODE_NAMES } from '../../../libs/modes/modes.ts'
import { historyTitle } from '../../../libs/historyTitle/historyTitle.ts'
import { timeAgo } from '../../../libs/timeAgo/timeAgo.ts'
import styles from './HistoryEntry.module.scss'

/** Matches the 36px tile the icon sits in. */
const ICON = 16

export interface HistoryEntryProps {
  readonly item: ResultListItem
  /** Whether this entry is the one awaiting a second click. */
  readonly confirming: boolean
  readonly onDelete: (id: string) => void
  /** Passed in so a feed of entries agrees on what "now" is. */
  readonly now: Date
}

export function HistoryEntry({
  item,
  confirming,
  onDelete,
  now,
}: HistoryEntryProps) {
  // The prompt is the fallback subtitle: it is what was asked for.
  const subtitle = item.subtitle ?? item.prompt

  return (
    <div className={styles.historyEntry}>
      <span className={styles.historyEntry__icon} title={MODE_NAMES[item.type]}>
        <ModeIcon mode={item.type} size={ICON} />
      </span>
      <span className={styles.historyEntry__body}>
        <Link to={`/result/${item.id}`} className={styles.historyEntry__title}>
          {historyTitle(item)}
        </Link>
        {item.artist && item.type !== 'album_recommendation' && (
          <span className={styles.historyEntry__artist}>{item.artist}</span>
        )}
        <span className={styles.historyEntry__subtitle}>{subtitle}</span>
      </span>
      <span className={styles.historyEntry__time}>
        {timeAgo(item.created_at, now)}
      </span>
      <button
        type="button"
        className={styles.historyEntry__delete}
        aria-label={
          confirming ? `Confirm deleting ${item.title}` : `Delete ${item.title}`
        }
        onClick={() => {
          onDelete(item.id)
        }}
      >
        {confirming ? 'Delete?' : '×'}
      </button>
    </div>
  )
}
