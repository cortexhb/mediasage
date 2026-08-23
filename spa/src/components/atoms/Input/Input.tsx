/**
 * A text control.
 *
 * Uncontrolled by design: the value is read from `FormData` on submit, so
 * typing never re-renders the page that holds it.
 */
import type { ComponentPropsWithoutRef } from 'react'

import styles from './Input.module.scss'

export type InputProps = Omit<ComponentPropsWithoutRef<'input'>, 'className'>

export function Input(props: InputProps) {
  return <input {...props} className={styles.input} />
}
