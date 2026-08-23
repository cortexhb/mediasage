/**
 * The music library: a select when a connected server has listed them, a
 * text field when it has not.
 *
 * The list comes from `/api/setup/status` and existed only inside the setup
 * wizard. Without it this is free text, where a typo reads as a library with
 * no tracks in it.
 */
import { Field } from '../Field/Field.tsx'
import { SelectField } from '../SelectField/SelectField.tsx'

export interface LibraryFieldProps {
  readonly value: string
  /** What Plex offers. Empty until a server is connected. */
  readonly libraries: readonly string[]
}

export function LibraryField({ value, libraries }: LibraryFieldProps) {
  if (libraries.length === 0) {
    return (
      <Field
        label="Music Library"
        name="music_library"
        defaultValue={value}
        placeholder="Music"
        hint="Connect to Plex to choose from the libraries it offers."
      />
    )
  }

  return (
    <SelectField
      label="Music Library"
      name="music_library"
      defaultValue={value}
      options={libraries.map((name) => ({ value: name, label: name }))}
    />
  )
}
