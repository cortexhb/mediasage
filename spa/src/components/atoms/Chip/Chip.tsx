/**
 * A toggle in a row of them, with the count it stands for.
 *
 * `frontend/app.js:770` drew these as plain buttons whose only state was a
 * `selected` class, so nothing announced which filter was in force.
 * `aria-pressed` is what makes that state real, and the stylesheet selects on
 * the attribute rather than on a second class.
 */
import styles from './Chip.module.scss'

export interface ChipProps {
  readonly selected: boolean
  /** Absent where there is no count to give: decades carry none. */
  readonly count?: number | null | undefined
  readonly onChoose: () => void
  readonly children: string
}

export function Chip({ selected, count, onChoose, children }: ChipProps) {
  return (
    <button
      type="button"
      className={styles.chip}
      aria-pressed={selected}
      onClick={onChoose}
    >
      {children}
      {count != null && (
        <>
          {' '}
          <span className={styles.chip__count}>{count}</span>
        </>
      )}
    </button>
  )
}
