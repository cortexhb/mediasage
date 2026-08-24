/**
 * A labelled input with its hint or its error: `Label`, `Input`, `Text`.
 *
 * The stack and the ids are `molecules/FieldShell`, which every labelled
 * control shares.
 */
import { Input } from '../../atoms/Input/Input.tsx'
import type { InputProps } from '../../atoms/Input/Input.tsx'
import { FieldShell } from '../FieldShell/FieldShell.tsx'

export interface FieldProps extends Omit<InputProps, 'id'> {
  readonly label: string
  /** Marks the label, for a value the server accepts without. */
  readonly optional?: boolean
  /** Shown under the input, for what the value means. */
  readonly hint?: string
  /** Shown under the input in the error colour, and announced. */
  readonly error?: string
}

export function Field({ label, optional, hint, error, ...input }: FieldProps) {
  return (
    <FieldShell label={label} optional={optional} hint={hint} error={error}>
      {({ id, describedBy }) => (
        <Input
          {...input}
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
      )}
    </FieldShell>
  )
}
