/**
 * A select over a list of values.
 *
 * Options are `{ value, label }` rather than children, so a caller mapping an
 * API list writes the list and not the markup.
 */
import type { ComponentPropsWithoutRef } from 'react'

import styles from './Select.module.scss'

export interface Option {
  readonly value: string
  readonly label: string
}

type ControlProps = Omit<
  ComponentPropsWithoutRef<'select'>,
  'className' | 'children'
>

export interface SelectProps extends ControlProps {
  readonly options: readonly Option[]
  /** Shown first with an empty value, for a choice not yet made. */
  readonly placeholder?: string
}

export function Select({ options, placeholder, ...control }: SelectProps) {
  return (
    <select {...control} className={styles.select}>
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}
