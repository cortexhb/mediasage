/**
 * One setting, drawn from what the API's schema says about it.
 *
 * A molecule, not an organism: it knows a field descriptor, not what any
 * particular setting means. `libs/patchFields` decided the control; this
 * only renders it.
 *
 * Every control is uncontrolled and defaults to the saved value, which is what
 * lets a save adopt the answer without moving anything the user typed.
 */
import type { PatchField } from '../../../libs/patchFields/patchFields.ts'
import { CheckboxField } from '../CheckboxField/CheckboxField.tsx'
import { Field } from '../Field/Field.tsx'

export interface SchemaFieldProps {
  readonly field: PatchField
  /** What the section currently holds, as `/api/config` reported it. */
  readonly value: unknown
}

export function SchemaField({ field, value }: SchemaFieldProps) {
  const shared = {
    label: field.label,
    name: field.name,
    ...(field.hint === undefined ? {} : { hint: field.hint }),
  }

  if (field.kind === 'boolean') {
    return <CheckboxField {...shared} defaultChecked={value === true} />
  }

  if (field.kind === 'password') {
    return (
      <Field
        {...shared}
        type="password"
        autoComplete="off"
        optional
        placeholder={value ? '••••••••  (configured)' : ''}
        hint={`${field.hint ?? ''} Leave blank to keep the stored value.`.trim()}
      />
    )
  }

  if (field.kind === 'number') {
    return (
      <Field
        {...shared}
        type="number"
        defaultValue={typeof value === 'number' ? value : ''}
        {...(field.min === undefined ? {} : { min: field.min })}
        {...(field.max === undefined ? {} : { max: field.max })}
        {...(field.step === undefined ? {} : { step: field.step })}
      />
    )
  }

  if (field.kind === 'list') {
    return (
      <Field
        {...shared}
        defaultValue={Array.isArray(value) ? value.join(', ') : ''}
        hint={`${field.hint ?? ''} Comma-separated.`.trim()}
      />
    )
  }

  return (
    <Field {...shared} defaultValue={typeof value === 'string' ? value : ''} />
  )
}
