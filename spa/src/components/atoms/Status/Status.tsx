/**
 * Whether something the app depends on is answering.
 *
 * `role="status"` because the value changes after a save without the page
 * reloading, and the change is the whole point of the indicator.
 */
import styles from './Status.module.scss'

export interface StatusProps {
  readonly state: 'connected' | 'error' | 'unknown'
  readonly children: string
}

export function Status({ state, children }: StatusProps) {
  return (
    <p className={styles.status} data-state={state} role="status">
      {children}
    </p>
  )
}
