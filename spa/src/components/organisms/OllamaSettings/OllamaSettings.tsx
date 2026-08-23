/**
 * Ollama: where the local server is, and which of its models to use.
 *
 * The endpoint is probed as it is typed, so a server can be pointed at and a
 * model chosen before anything is saved — `frontend/app.js:2727` did the same
 * with a 500 ms debounce. The model fields are selects because this is the
 * one provider that reports what it holds.
 *
 * One probe answers everything, and the analysis model rides along in it. A
 * second fetcher driven by a second effect looked tidier and did not work:
 * React Router dispatches fetcher data inside a transition, and a `setState`
 * in the load's continuation restarts that render, losing the dependency
 * comparison of every effect — so nothing keyed on the new data fired again.
 * Nothing here may call `setState` on the success path of a load.
 *
 * The context window is the one value discovered rather than typed. It is
 * submitted only when this server reported it for the model in force; the
 * saved figure is shown as a default otherwise, and left alone.
 */
import { useEffect, useState } from 'react'
import { useFetcher } from 'react-router'

import { offeredModels } from '../../../libs/offeredModels/offeredModels.ts'
import type { OllamaProbe } from '../../../libs/probeOllama/probeOllama.ts'
import { tracksThatFit } from '../../../libs/tracksThatFit/tracksThatFit.ts'
import { useDebounced } from '../../../libs/useDebounced/useDebounced.ts'
import { Input } from '../../atoms/Input/Input.tsx'
import { Status } from '../../atoms/Status/Status.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import { Field } from '../../molecules/Field/Field.tsx'
import { SelectField } from '../../molecules/SelectField/SelectField.tsx'

/** Where Ollama listens unless it was told otherwise. */
const DEFAULT_URL = 'http://localhost:11434'

/** The resource route the probe goes through. */
const PROBE = '/settings/ollama'

export interface OllamaSettingsProps {
  readonly endpoint: string | undefined
  readonly analysis: string
  readonly generation: string
  readonly contextWindow: number
}

export function OllamaSettings({
  endpoint,
  analysis,
  generation,
  contextWindow,
}: OllamaSettingsProps) {
  const [url, setUrl] = useState(endpoint ?? DEFAULT_URL)
  const [picked, setPicked] = useState({ analysis, generation })
  const settled = useDebounced(url)
  const probe = useFetcher<OllamaProbe>()
  // Destructured: `load` is stable, the fetcher it came from is not.
  const { load: ask } = probe

  /** Both what the server holds and the window in force, in one load. */
  const inspect = (address: string, want: string, alt: string) => {
    const asked = new URLSearchParams({ url: address, want, alt })
    // No success handler: a `setState` here would break every effect below.
    ask(`${PROBE}?${asked.toString()}`).catch(() => undefined)
  }

  useEffect(() => {
    if (settled.trim() === '') return
    const asked = new URLSearchParams({
      url: settled,
      want: analysis,
      alt: generation,
    })
    ask(`${PROBE}?${asked.toString()}`).catch(() => undefined)
  }, [settled, analysis, generation, ask])

  const models = probe.data?.models ?? []
  const options = models.map((name) => ({ value: name, label: name }))
  const chosen = offeredModels(models, picked.analysis, picked.generation)

  // Found only if read for the model now in force.
  const found =
    probe.data?.described !== undefined &&
    probe.data.described === chosen.analysis
      ? probe.data.contextWindow
      : undefined
  const shown = found ?? contextWindow

  const checking = probe.state !== 'idle'
  const reported = probe.data?.message ?? 'Not checked'

  return (
    <>
      <Field
        label="Ollama URL"
        name="endpoint_url"
        type="url"
        value={url}
        onChange={(event) => {
          setUrl(event.target.value)
        }}
        placeholder={DEFAULT_URL}
        hint="Models load from this server as you type it."
      />
      <Status
        state={
          checking ? 'unknown' : probe.data?.connected ? 'connected' : 'error'
        }
      >
        {checking ? 'Checking…' : reported}
      </Status>
      <SelectField
        label="Analysis Model"
        name="model_analysis"
        value={chosen.analysis}
        onChange={(event) => {
          const model = event.target.value
          setPicked((was) => ({ ...was, analysis: model }))
          // Re-probed: the window shown belongs to the analysis model.
          inspect(settled, model, chosen.generation)
        }}
        options={options}
        placeholder="-- Select model --"
        disabled={options.length === 0}
      />
      <SelectField
        label="Generation Model"
        name="model_generation"
        value={chosen.generation}
        onChange={(event) => {
          setPicked((was) => ({ ...was, generation: event.target.value }))
        }}
        options={options}
        placeholder="-- Select model --"
        disabled={options.length === 0}
      />
      {found !== undefined && (
        <Input type="hidden" name="context_window" value={found} readOnly />
      )}
      <Text tone="muted">
        Context window: {shown.toLocaleString()} tokens
        {found === undefined && ' (default)'} (~
        {tracksThatFit(shown).toLocaleString()} tracks)
      </Text>
    </>
  )
}
