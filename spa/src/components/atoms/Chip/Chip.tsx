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
  /**
   * `radio` for one of a set where exactly one holds.
   *
   * `frontend/index.html:610` draws the play-history pills as a radiogroup of
   * chips; a filter chip is a toggle, and toggles are the default.
   */
  readonly as?: 'toggle' | 'radio'
  readonly onChoose: () => void
  readonly children: string
}

export function Chip({
  selected,
  count,
  as = 'toggle',
  onChoose,
  children,
}: ChipProps) {
  const state =
    as === 'radio'
      ? { role: 'radio', 'aria-checked': selected }
      : { 'aria-pressed': selected }

  return (
    <button type="button" className={styles.chip} {...state} onClick={onChoose}>
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
