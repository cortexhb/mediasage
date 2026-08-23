/**
 * The LLM half of Settings: which provider, and whatever that provider needs.
 *
 * The provider select is the one controlled input on the page, because it
 * decides which fields exist. Everything under it is uncontrolled and read
 * from `FormData` on submit.
 */
import { useState } from 'react'

import type { ConfigResponse } from '../../../api/generated/types.gen.ts'
import { Input } from '../../atoms/Input/Input.tsx'
import { Status } from '../../atoms/Status/Status.tsx'
import { Section } from '../../molecules/Section/Section.tsx'
import { SelectField } from '../../molecules/SelectField/SelectField.tsx'
import { CloudSettings } from '../CloudSettings/CloudSettings.tsx'
import { CustomSettings } from '../CustomSettings/CustomSettings.tsx'
import { OllamaSettings } from '../OllamaSettings/OllamaSettings.tsx'

/** What the select offers, in the order `frontend/index.html:31` lists. */
const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'openai', label: 'OpenAI (GPT)' },
  { value: 'gemini', label: 'Google (Gemini)' },
  { value: 'ollama', label: 'Ollama (Local)' },
  { value: 'custom', label: 'Custom (OpenAI-compatible)' },
]

/** The providers reached by API key rather than by endpoint. */
const CLOUD = new Set(['anthropic', 'openai', 'gemini'])

/** Shown where a credential is already stored, in place of its value. */
const STORED = '••••••••••••••••  (configured)'

export interface ProviderSettingsProps {
  readonly config: ConfigResponse
}

export function ProviderSettings({ config }: ProviderSettingsProps) {
  const [provider, setProvider] = useState(config.llm_provider)

  return (
    <Section title="LLM Provider">
      <Status state={config.llm_configured ? 'connected' : 'unknown'}>
        {config.llm_configured ? 'Configured' : 'Not configured'}
      </Status>

      <SelectField
        label="Provider"
        name="llm_provider"
        options={PROVIDERS}
        value={provider}
        disabled={config.provider_from_env}
        onChange={(event) => {
          setProvider(event.target.value)
        }}
        {...(config.provider_from_env && {
          hint: 'Set by LLM_PROVIDER. Edit .env to change it.',
        })}
      />
      {config.provider_from_env && (
        // A disabled control is absent from FormData; the save needs it.
        <Input type="hidden" name="llm_provider" value={provider} readOnly />
      )}

      {CLOUD.has(provider) && (
        <CloudSettings
          analysis={config.model_analysis}
          generation={config.model_generation}
          smart={config.smart_generation ?? false}
          contextWindow={config.context_window}
          keySet={config.llm_api_key_set}
          stored={STORED}
        />
      )}

      {provider === 'ollama' && (
        <OllamaSettings
          endpoint={config.endpoint_url}
          analysis={config.model_analysis}
          generation={config.model_generation}
          contextWindow={config.context_window}
        />
      )}

      {provider === 'custom' && (
        <CustomSettings
          endpoint={config.endpoint_url}
          model={config.model_analysis}
          contextWindow={config.context_window}
          keySet={config.llm_api_key_set}
          stored={STORED}
        />
      )}
    </Section>
  )
}
