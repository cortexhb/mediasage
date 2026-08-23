/**
 * A hosted provider: Anthropic, OpenAI or Gemini.
 *
 * The legacy screen offered only an API key here (`frontend/index.html:682`),
 * which left the two model names and the context window reachable solely
 * through `config.user.yaml` or the environment. They are required to run a
 * generation, so they belong on the form.
 *
 * Model names are typed rather than chosen: none of these providers publishes
 * a list the app could offer, and a table of names in the code would go stale.
 */
import { useState } from 'react'

import {
  contextWindowError,
  LARGEST,
  SMALLEST,
} from '../../../libs/contextWindowError/contextWindowError.ts'
import { tracksThatFit } from '../../../libs/tracksThatFit/tracksThatFit.ts'
import { CheckboxField } from '../../molecules/CheckboxField/CheckboxField.tsx'
import { Field } from '../../molecules/Field/Field.tsx'

/** Said where the analysis model is doing the generating as well. */
const IGNORED = 'Ignored: the analysis model is generating.'

export interface CloudSettingsProps {
  readonly analysis: string
  readonly generation: string
  readonly smart: boolean
  readonly contextWindow: number
  readonly keySet: boolean
  /** Shown in place of a stored credential's value. */
  readonly stored: string
}

export function CloudSettings({
  analysis,
  generation,
  smart,
  contextWindow,
  keySet,
  stored,
}: CloudSettingsProps) {
  const [window, setWindow] = useState(String(contextWindow))
  const [smartOn, setSmartOn] = useState(smart)

  const error = contextWindowError(window)
  const fits = tracksThatFit(Number.parseInt(window, 10) || contextWindow)

  return (
    <>
      <Field
        label="API Key"
        name="llm_api_key"
        type="password"
        autoComplete="off"
        placeholder={keySet ? stored : 'Your API key'}
        hint="Leave blank to keep the stored key."
      />
      <Field
        label="Analysis Model"
        name="model_analysis"
        defaultValue={analysis}
        placeholder="model-name"
        hint="Picks the tracks. The stronger model belongs here."
      />
      <Field
        label="Generation Model"
        name="model_generation"
        defaultValue={generation}
        placeholder="model-name"
        // Read-only, not disabled: a disabled field is absent from FormData.
        readOnly={smartOn}
        hint={smartOn ? IGNORED : 'Writes the playlist. A cheaper model does.'}
      />
      <CheckboxField
        label="Use the analysis model for generation"
        name="smart_generation"
        checked={smartOn}
        onChange={(event) => {
          setSmartOn(event.target.checked)
        }}
        hint="Better playlists, at the analysis model's price."
      />
      <Field
        label="Context Window"
        name="context_window"
        type="number"
        min={SMALLEST}
        max={LARGEST}
        required
        value={window}
        onChange={(event) => {
          setWindow(event.target.value)
        }}
        {...(error === undefined
          ? { hint: `~${fits.toLocaleString()} tracks fit in it` }
          : { error })}
      />
    </>
  )
}
