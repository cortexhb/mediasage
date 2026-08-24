/**
 * How many tokens the model can be sent, and what that buys in tracks.
 *
 * Every provider the app reaches by key or by endpoint requires this of the
 * caller, because none of them reports it -- only Ollama does, and that one
 * discovers the figure instead (`organisms/OllamaSettings`).
 *
 * It is checked as it is edited, because a save answers one 422 for the whole
 * form and cannot say which field was at fault. The hint says what the number
 * means rather than repeating it.
 */
import {
  LARGEST,
  SMALLEST,
} from '../../../libs/contextWindowError/contextWindowError.ts'
import { tracksThatFit } from '../../../libs/tracksThatFit/tracksThatFit.ts'
import { Field } from '../Field/Field.tsx'

export interface ContextWindowFieldProps {
  /** The typed value, which is a string because a part-typed number is one. */
  readonly value: string
  readonly onChange: (value: string) => void
  /** What the saved configuration holds, for a value that will not parse. */
  readonly saved: number
  /** What is wrong with the value, where something is. */
  readonly error?: string | undefined
}

export function ContextWindowField({
  value,
  onChange,
  saved,
  error,
}: ContextWindowFieldProps) {
  const fits = tracksThatFit(Number.parseInt(value, 10) || saved)

  return (
    <Field
      label="Context Window"
      name="context_window"
      type="number"
      // Constraints, not decoration: they are what blocks an invalid submit.
      min={SMALLEST}
      max={LARGEST}
      required
      value={value}
      onChange={(event) => {
        onChange(event.target.value)
      }}
      {...(error === undefined
        ? { hint: `~${fits.toLocaleString()} tracks fit in it` }
        : { error })}
    />
  )
}
