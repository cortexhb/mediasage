/**
 * A paragraph.
 *
 * `id` is exposed because a hint or an error is pointed at by an input's
 * `aria-describedby`, and `role` because an error that appears after the page
 * has loaded has to announce itself.
 */
import styles from './Text.module.scss'

export interface TextProps {
  /** Omitted for body copy, which inherits the document's colour. */
  readonly tone?: 'muted' | 'secondary' | 'error' | 'success'
  readonly id?: string
  readonly role?: 'alert' | 'status'
  readonly children: React.ReactNode
}

export function Text({ tone, id, role, children }: TextProps) {
  return (
    <p className={styles.text} data-tone={tone} id={id} role={role}>
      {children}
    </p>
  )
}
