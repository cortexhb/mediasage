/**
 * The stack every labelled control sits in: label, control, hint or error.
 *
 * Replaces the legacy `.form-group` triple, which hand-maintained the `for`
 * and `id` pair on every field. `useId` supplies both here, and the control is
 * a function so that it can be given the two ids it has to carry.
 *
 * `molecules/Field`, `molecules/SelectField` and `molecules/CheckboxField` are
 * what pages use; each is this shell around one atom.
 */
import type { ReactNode } from 'react'
import { useId } from 'react'

import { Label } from '../../atoms/Label/Label.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import styles from './FieldShell.module.scss'

/** What the control has to carry, so the label and the hint reach it. */
export interface FieldIds {
  readonly id: string
  /** Undefined where there is nothing under the control to point at. */
  readonly describedBy: string | undefined
}

export interface FieldShellProps {
  readonly label: string
  /** Marks the label, for a value the server accepts without. */
  readonly optional?: boolean | undefined
  /** Shown under the control, for what the value means. */
  readonly hint?: string | undefined
  /** Shown under the control in the error colour, and announced. */
  readonly error?: string | undefined
  /** Label beside the control rather than above it, as a checkbox wants. */
  readonly beside?: boolean | undefined
  readonly children: (ids: FieldIds) => ReactNode
}

export function FieldShell({
  label,
  optional,
  hint,
  error,
  beside,
  children,
}: FieldShellProps) {
  const id = useId()
  const described = useId()
  const ids: FieldIds = {
    id,
    describedBy: (error ?? hint) ? described : undefined,
  }

  const labelled = (
    <Label htmlFor={id} optional={optional}>
      {label}
    </Label>
  )

  return (
    <div className={styles.fieldShell}>
      {beside ? (
        <div className={styles.fieldShell__row}>
          {children(ids)}
          {labelled}
        </div>
      ) : (
        <>
          {labelled}
          {children(ids)}
        </>
      )}
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
