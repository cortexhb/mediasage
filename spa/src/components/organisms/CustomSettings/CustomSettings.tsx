/**
 * Any OpenAI-compatible server: MLX, LM Studio, OpenRouter, vLLM.
 *
 * The context window is typed rather than discovered — nothing here exposes
 * an equivalent of Ollama's `/api/show`, which is why the field exists at all
 * and why the API requires it of every provider. It is checked as it is
 * edited, because a save answers one 422 for the whole form and cannot say
 * which field was at fault.
 */
import { useState } from 'react'

import { customErrors } from '../../../libs/customErrors/customErrors.ts'
import { ContextWindowField } from '../../molecules/ContextWindowField/ContextWindowField.tsx'
import { Field } from '../../molecules/Field/Field.tsx'

export interface CustomSettingsProps {
  readonly endpoint: string | undefined
  readonly model: string
  readonly contextWindow: number
  readonly keySet: boolean
  /** Shown in place of a stored credential's value. */
  readonly stored: string
}

export function CustomSettings({
  endpoint,
  model,
  contextWindow,
  keySet,
  stored,
}: CustomSettingsProps) {
  const [url, setUrl] = useState(endpoint ?? '')
  const [window, setWindow] = useState(String(contextWindow))
  // The address is only judged once it has been left, not mid-hostname.
  const [urlVisited, setUrlVisited] = useState(false)

  const errors = customErrors(url, window)

  return (
    <>
      <Field
        label="API Base URL"
        name="endpoint_url"
        type="url"
        value={url}
        onChange={(event) => {
          setUrl(event.target.value)
        }}
        onBlur={() => {
          setUrlVisited(true)
        }}
        placeholder="http://localhost:5000/v1"
        required
        {...(urlVisited && errors.url !== undefined && { error: errors.url })}
      />
      <Field
        label="API Key"
        name="llm_api_key"
        type="password"
        autoComplete="off"
        optional
        placeholder={keySet ? stored : 'sk-…'}
      />
      <Field
        label="Model Name"
        name="model_analysis"
        defaultValue={model}
        placeholder="model-name"
        hint="Used for analysis and for generation both."
      />
      <ContextWindowField
        value={window}
        onChange={setWindow}
        saved={contextWindow}
        error={errors.contextWindow}
      />
    </>
  )
}
