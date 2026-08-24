/**
 * A labelled checkbox with its hint: `Checkbox`, `Label`, `Text`.
 *
 * The label sits beside the control rather than above it, which is the one way
 * this differs from `molecules/Field`; the stack is `molecules/FieldShell` for
 * both.
 *
 * A hidden `false` precedes the checkbox, because an unchecked box is absent
 * from `FormData` entirely and the save would read that as "unchanged" rather
 * than as "off". Both carry the same name; the later entry wins.
 */
import { Checkbox } from '../../atoms/Checkbox/Checkbox.tsx'
import type { CheckboxProps } from '../../atoms/Checkbox/Checkbox.tsx'
import { FieldShell } from '../FieldShell/FieldShell.tsx'

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
  return (
    <FieldShell label={label} hint={hint} beside>
      {({ id, describedBy }) => (
        <>
          <input type="hidden" name={name} value="false" />
          <Checkbox
            {...control}
            id={id}
            name={name}
            value="true"
            aria-describedby={describedBy}
          />
        </>
      )}
    </FieldShell>
  )
}
