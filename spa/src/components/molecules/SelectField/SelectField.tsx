/**
 * A labelled select with its hint: `Label`, `Select`, `Text`.
 */
import { useId } from 'react'

import { Select } from '../../atoms/Select/Select.tsx'
import type { SelectProps } from '../../atoms/Select/Select.tsx'
import { Label } from '../../atoms/Label/Label.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import styles from './SelectField.module.scss'

export interface SelectFieldProps extends Omit<SelectProps, 'id'> {
  readonly label: string
  /** Shown under the control, for what the value means. */
  readonly hint?: string
}

export function SelectField({ label, hint, ...control }: SelectFieldProps) {
  const id = useId()
  const described = useId()

  return (
    <div className={styles.selectField}>
      <Label htmlFor={id}>{label}</Label>
      <Select
        {...control}
        id={id}
        aria-describedby={hint ? described : undefined}
      />
      {hint && (
        <Text tone="muted" id={described}>
          {hint}
        </Text>
      )}
    </div>
  )
}
