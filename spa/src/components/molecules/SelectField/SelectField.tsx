/**
 * A labelled select with its hint: `Label`, `Select`, `Text`.
 *
 * The stack and the ids are `molecules/FieldShell`.
 */
import { Select } from '../../atoms/Select/Select.tsx'
import type { SelectProps } from '../../atoms/Select/Select.tsx'
import { FieldShell } from '../FieldShell/FieldShell.tsx'

export interface SelectFieldProps extends Omit<SelectProps, 'id'> {
  readonly label: string
  /** Shown under the control, for what the value means. */
  readonly hint?: string
}

export function SelectField({ label, hint, ...control }: SelectFieldProps) {
  return (
    <FieldShell label={label} hint={hint}>
      {({ id, describedBy }) => (
        <Select {...control} id={id} aria-describedby={describedBy} />
      )}
    </FieldShell>
  )
}
