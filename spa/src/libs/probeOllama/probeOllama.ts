/**
 * What a local Ollama server reports, for an endpoint that is not saved yet.
 *
 * A resource route rather than a fetch inside a component: the probe is a
 * cheap idempotent read, and a fetcher supersedes its own in-flight load, so
 * a URL typed one character at a time cannot land out of order.
 *
 * One question, one answer: the server, the models it holds, and the context
 * window of the model that will end up in force. `want` is the saved analysis
 * model and `alt` the saved generation one, because which model that is
 * depends on both — `offeredModels` decides it, and this must agree.
 *
 * A window is only ever reported alongside the model it was read from, so the
 * form cannot show one model's window against another's name.
 */
import type { LoaderFunctionArgs } from 'react-router'

import {
  listOllamaModels,
  readOllamaModelInfo,
  readOllamaStatus,
} from '../../api/config/config.ts'

export interface OllamaProbe {
  /** Whether the endpoint is usable: reachable, and holding models. */
  readonly connected: boolean
  /** The status line, whether that is a count or a reason. */
  readonly message: string
  readonly models: readonly string[]
  /** The model `contextWindow` belongs to, so it cannot be read as another's. */
  readonly described: string | undefined
  /** Absent when the server does not report one for `described`. */
  readonly contextWindow: number | undefined
}

/** Nothing was asked, so nothing is reported. */
const NOTHING: OllamaProbe = {
  connected: false,
  message: '',
  models: [],
  described: undefined,
  contextWindow: undefined,
}

/**
 * The context window, or nothing.
 *
 * Swallows its failure: a server that lists a model but will not describe it
 * still leaves the endpoint usable, and the saved figure stands.
 */
async function modelWindow(
  url: string,
  model: string,
  signal: AbortSignal,
): Promise<number | undefined> {
  try {
    const info = await readOllamaModelInfo(url, model, signal)
    return info.context_window ?? undefined
  } catch {
    return undefined
  }
}

/** The server, what it has pulled, and the window of the model in force. */
async function serverModels(
  url: string,
  want: string,
  alt: string,
  signal: AbortSignal,
): Promise<OllamaProbe> {
  const status = await readOllamaStatus(url, signal)
  if (!status.connected) {
    return { ...NOTHING, message: status.error ?? 'Connection failed' }
  }

  const count = status.model_count ?? 0
  if (count === 0) {
    // Reachable but useless, which the legacy screen also treats as an error.
    return { ...NOTHING, message: 'No models installed' }
  }

  const listed = await listOllamaModels(url, signal)
  const models = (listed.models ?? []).map((model) => model.name)
  const held = (name: string) => models.find((model) => model === name)
  // `offeredModels` fills the form by this rule; the window must match it.
  const described =
    held(want) ?? (held(alt) === undefined ? models[0] : undefined)

  return {
    connected: true,
    message: listed.error ?? `Connected (${String(count)} models)`,
    models,
    described,
    contextWindow:
      described === undefined
        ? undefined
        : await modelWindow(url, described, signal),
  }
}

export async function probeOllama({
  request,
}: LoaderFunctionArgs): Promise<OllamaProbe> {
  const asked = new URL(request.url).searchParams
  const url = asked.get('url')?.trim() ?? ''
  const want = asked.get('want')?.trim() ?? ''
  const alt = asked.get('alt')?.trim() ?? ''

  if (url === '') return NOTHING

  try {
    return await serverModels(url, want, alt, request.signal)
  } catch {
    // Never thrown onward: a bad address must not replace the settings form.
    return { ...NOTHING, message: 'Connection failed' }
  }
}
