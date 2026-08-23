/**
 * A labelled checkbox with its hint: `Checkbox`, `Label`, `Text`.
 *
 * The label sits beside the control rather than above it, which is the one
 * way this differs from `Field`.
 *
 * A hidden `false` precedes the checkbox, because an unchecked box is absent
 * from `FormData` entirely and the save would read that as "unchanged" rather
 * than as "off". Both carry the same name; the later entry wins.
 */
import { useId } from 'react'

import { Checkbox } from '../../atoms/Checkbox/Checkbox.tsx'
import type { CheckboxProps } from '../../atoms/Checkbox/Checkbox.tsx'
import { Label } from '../../atoms/Label/Label.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import styles from './CheckboxField.module.scss'

export interface CheckboxFieldProps extends Omit<
  CheckboxProps,
  'id' | 'value'
> {
  readonly label: string
  readonly name: string
  /** Shown under the control, for what turning it on does. */
  readonly hint?: string
}

export function CheckboxField({
  label,
  name,
  hint,
  ...control
}: CheckboxFieldProps) {
  const id = useId()
  const described = useId()

  return (
    <div className={styles.checkboxField}>
      <input type="hidden" name={name} value="false" />
      <div className={styles.checkboxField__row}>
        <Checkbox
          {...control}
          id={id}
          name={name}
          value="true"
          aria-describedby={hint ? described : undefined}
        />
        <Label htmlFor={id}>{label}</Label>
      </div>
      {hint && (
        <Text tone="muted" id={described}>
          {hint}
        </Text>
      )}
    </div>
  )
}
