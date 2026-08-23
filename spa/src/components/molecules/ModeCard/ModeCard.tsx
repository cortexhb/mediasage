/**
 * One of the three things Home offers, as a card-sized link.
 *
 * `frontend/index.html:186` drew these as `<button data-nav="…">` and routed
 * them through a click handler, so they could not be opened in a new tab or
 * read as destinations. They are links here because that is what they are.
 */
import { Link } from 'react-router'

import { ModeIcon } from '../../atoms/ModeIcon/ModeIcon.tsx'
import type { Mode } from '../../../libs/modes/modes.ts'
import styles from './ModeCard.module.scss'

/** The home cards draw the icon at 40px; the feed uses the same shapes at 16. */
const ICON = 40

export interface ModeCardProps {
  readonly to: string
  readonly mode: Mode
  readonly title: string
  readonly description: string
  /** Whether the destination is unusable, so far as the caller knows. */
  readonly disabled?: boolean
}

export function ModeCard({
  to,
  mode,
  title,
  description,
  disabled = false,
}: ModeCardProps) {
  return (
    <Link
      to={to}
      className={styles.modeCard}
      // Dropping `to` instead would leave the tab order and the link role.
      aria-disabled={disabled}
      data-disabled={disabled}
      onClick={(event) => {
        if (disabled) event.preventDefault()
      }}
    >
      <span className={styles.modeCard__icon}>
        <ModeIcon mode={mode} size={ICON} />
      </span>
      <span className={styles.modeCard__title}>{title}</span>
      <span className={styles.modeCard__description}>{description}</span>
    </Link>
  )
}
