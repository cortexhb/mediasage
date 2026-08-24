/**
 * A row of mutually exclusive choices, as buttons.
 *
 * `frontend/index.html:352` drew three of these -- playlist size, minimum
 * rating, max tracks to AI -- as `.count-btn`, `.rating-btn` and `.limit-btn`.
 * Two appearances, not three: size splits the row evenly, the other two are
 * smaller and wrap. `spread` is which.
 *
 * Buttons rather than a `<select>`: every option is worth seeing at once.
 * `aria-pressed` carries the state, as in `atoms/Chip`.
 */
import { Heading } from '../../atoms/Heading/Heading.tsx'
import styles from './ChoiceRow.module.scss'

export interface Choice {
  readonly value: number
  readonly label: string
}

export interface ChoiceRowProps {
  readonly title: string
  /** Shown under the title, for what the choice costs or means. */
  readonly hint?: string
  readonly choices: readonly Choice[]
  readonly value: number
  /** `even` splits the row; `wrap` keeps each option its own width. */
  readonly spread: 'even' | 'wrap'
  readonly onChoose: (value: number) => void
}

export function ChoiceRow({
  title,
  hint,
  choices,
  value,
  spread,
  onChoose,
}: ChoiceRowProps) {
  return (
    <div className={styles.choiceRow}>
      <Heading level={3}>{title}</Heading>
      {hint && <p className={styles.choiceRow__hint}>{hint}</p>}
      <div
        className={styles.choiceRow__options}
        data-spread={spread}
        role="group"
        aria-label={title}
      >
        {choices.map((choice) => (
          <button
            key={choice.value}
            type="button"
            className={styles.choiceRow__option}
            aria-pressed={choice.value === value}
            onClick={() => {
              onChoose(choice.value)
            }}
          >
            {choice.label}
          </button>
        ))}
      </div>
    </div>
  )
}
