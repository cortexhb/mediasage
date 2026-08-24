/**
 * The segmented control that picks where a round draws its albums from.
 *
 * Ports `.rec-mode-control` (`frontend/index.html:576`). `aria-pressed`
 * carries the state, as in `atoms/Chip`, and the stylesheet selects on the
 * attribute rather than on a second class.
 */
import type { RecommendMode } from '../../../libs/albumStore/albumStore.ts'
import styles from './ModeSwitch.module.scss'

/** The two, worded as `frontend/index.html:577` words them. */
const MODES: readonly {
  readonly value: RecommendMode
  readonly label: string
}[] = [
  { value: 'library', label: 'From My Library' },
  { value: 'discovery', label: 'Something New' },
]

export interface ModeSwitchProps {
  readonly value: RecommendMode
  readonly onChoose: (mode: RecommendMode) => void
}

export function ModeSwitch({ value, onChoose }: ModeSwitchProps) {
  return (
    <div
      className={styles.modeSwitch}
      role="group"
      aria-label="Recommendation mode"
    >
      {MODES.map((mode) => (
        <button
          key={mode.value}
          type="button"
          className={styles.modeSwitch__option}
          aria-pressed={mode.value === value}
          onClick={() => {
            onChoose(mode.value)
          }}
        >
          {mode.label}
        </button>
      ))}
    </div>
  )
}
