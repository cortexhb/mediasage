/**
 * How far along something is, or that it is under way at all.
 *
 * A null `percent` is indeterminate: the bar animates a travelling sliver and
 * carries no `aria-valuenow`, which is how ARIA says "running, unmeasured". A
 * zero-width bar would say "stalled" to both a reader and a screen reader.
 *
 * The fill's width is the one inline style in the app: it is a continuous
 * value, so there is no class it could be looked up from.
 */
import styles from './ProgressBar.module.scss'

export interface ProgressBarProps {
  /** Percent complete, or null where nothing can be measured yet. */
  readonly percent: number | null
  readonly label: string
}

export function ProgressBar({ percent, label }: ProgressBarProps) {
  const measured = percent !== null
  // Clamped: a sync can process more than its first counted total.
  const filled = measured ? Math.max(0, Math.min(100, Math.round(percent))) : 0

  return (
    <div
      className={styles.progressBar}
      role="progressbar"
      aria-label={label}
      aria-valuenow={measured ? filled : undefined}
      aria-valuemin={0}
      aria-valuemax={100}
      data-indeterminate={measured ? undefined : 'true'}
    >
      <div
        className={styles.progressBar__fill}
        style={measured ? { width: `${String(filled)}%` } : undefined}
      />
    </div>
  )
}
