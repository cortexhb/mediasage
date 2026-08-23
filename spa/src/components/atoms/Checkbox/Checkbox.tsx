/**
 * A checkbox.
 *
 * Separate from `Input`, which styles a text control full-width; a checkbox
 * is sized to itself and sits beside its label rather than under it.
 */
import type { ComponentPropsWithoutRef } from 'react'

import styles from './Checkbox.module.scss'

export type CheckboxProps = Omit<
  ComponentPropsWithoutRef<'input'>,
  'className' | 'type'
>

export function Checkbox(props: CheckboxProps) {
  return <input {...props} type="checkbox" className={styles.checkbox} />
}
