/**
 * A labelled input with its hint or its error: `Label`, `Input`, `Text`.
 *
 * Replaces the legacy `.form-group` triple, which hand-maintained the `for`
 * and `id` pair on every field. `useId` supplies both here.
 */
import { useId } from 'react'

import { Input } from '../../atoms/Input/Input.tsx'
import type { InputProps } from '../../atoms/Input/Input.tsx'
import { Label } from '../../atoms/Label/Label.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import styles from './Field.module.scss'

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
  const id = useId()
  const described = useId()

  return (
    <div className={styles.field}>
      <Label htmlFor={id} optional={optional}>
        {label}
      </Label>
      <Input
        {...input}
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={(hint ?? error) ? described : undefined}
      />
      {error ? (
        <Text tone="error" id={described} role="alert">
          {error}
        </Text>
      ) : (
        hint && (
          <Text tone="muted" id={described}>
            {hint}
          </Text>
        )
      )}
    </div>
  )
}
