/**
 * A form label, tied to its control by id.
 *
 * `htmlFor` is required rather than optional: a label that wraps its control
 * works for a mouse but leaves the accessible name to the browser's
 * heuristics, and every control here has an id from `useId` anyway.
 */
import styles from './Label.module.scss'

export interface LabelProps {
  readonly htmlFor: string
  /** Marks the label, for a value the server accepts without. */
  readonly optional?: boolean | undefined
  readonly children: string
}

export function Label({ htmlFor, optional, children }: LabelProps) {
  return (
    <label className={styles.label} htmlFor={htmlFor}>
      {children}
      {optional && <span className={styles.label__optional}> (optional)</span>}
    </label>
  )
}
