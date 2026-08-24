/**
 * A multi-line text control.
 *
 * Uncontrolled like `atoms/Input`: the value is read from `FormData` on
 * submit, so typing a long prompt never re-renders the page around it.
 */
import type { ComponentProps } from 'react'

import styles from './Textarea.module.scss'

// `ComponentProps`, not `…WithoutRef`: React 19 passes `ref` as a prop, and
// a suggestion pill writes into the box through one.
export type TextareaProps = Omit<ComponentProps<'textarea'>, 'className'>

export function Textarea(props: TextareaProps) {
  return <textarea {...props} className={styles.textarea} />
}
