/**
 * One aspect of a seed track, offered as a thing to explore.
 *
 * Ports `.dimension-card` (`frontend/app.js:2996`), which carried
 * `role="checkbox"` and toggled on click, Enter and Space. Selection is held
 * by the step and submitted as hidden inputs, as the filters step does with
 * its chips, so this draws state rather than owning it.
 */
import type { Dimension } from '../../../api/generated/types.gen.ts'
import styles from './DimensionCard.module.scss'

export interface DimensionCardProps {
  readonly dimension: Dimension
  readonly selected: boolean
  readonly onToggle: () => void
}

export function DimensionCard({
  dimension,
  selected,
  onToggle,
}: DimensionCardProps) {
  return (
    <div
      className={styles.dimensionCard}
      role="checkbox"
      tabIndex={0}
      aria-checked={selected}
      aria-label={`${dimension.label}: ${dimension.description}`}
      onClick={onToggle}
      onKeyDown={(event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return
        event.preventDefault()
        onToggle()
      }}
    >
      <div className={styles.dimensionCard__label}>{dimension.label}</div>
      <div className={styles.dimensionCard__description}>
        {dimension.description}
      </div>
    </div>
  )
}
