/**
 * The settings endpoints, paired with their generated types.
 *
 * One wrapper per resource, beside nothing else: `src/api/` never grows a
 * table of every endpoint. A field renamed in `backend/` becomes a compile
 * error here rather than a blank panel.
 *
 * `ConfigUpdateWritable` is the request shape, not `ConfigUpdate`. Codegen
 * splits the two because `SecretStr` is write-only: the read type carries
 * `plex_token?: null`, which cannot express sending one.
 */
import type {
  ConfigResponse,
  ConfigUpdateWritable,
  OllamaModelInfo,
  OllamaModelsResponse,
  OllamaStatus,
  SetupStatusResponse,
} from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/** `GET /api/config` — the current settings, with no credential in them. */
export function readConfig(signal: AbortSignal): Promise<ConfigResponse> {
  return request<ConfigResponse>('/api/config', { signal })
}

/**
 * `POST /api/config` — prove the change works, then keep it.
 *
 * Answers 422 when a probe refuses, which the form shows rather than
 * treating as a failure of the request itself.
 */
export function saveConfig(
  changes: ConfigUpdateWritable,
  signal: AbortSignal,
): Promise<ConfigResponse> {
  return request<ConfigResponse>('/api/config', {
    method: 'POST',
    body: changes,
    signal,
  })
}

/**
 * `GET /api/setup/status` — what Settings needs and `/api/config` does not
 * carry: the library list, the from-env flags, and the data directory.
 */
export function readSetupStatus(
  signal: AbortSignal,
): Promise<SetupStatusResponse> {
  return request<SetupStatusResponse>('/api/setup/status', { signal })
}

/**
 * `GET /api/ollama/status` — whether a local server answers.
 *
 * The url is a query parameter so an endpoint can be probed before it is
 * saved. An empty one falls back to the configured endpoint.
 */
export function readOllamaStatus(
  url: string,
  signal: AbortSignal,
): Promise<OllamaStatus> {
  return request<OllamaStatus>('/api/ollama/status', { query: { url }, signal })
}

/** `GET /api/ollama/models` — what that server has pulled. */
export function listOllamaModels(
  url: string,
  signal: AbortSignal,
): Promise<OllamaModelsResponse> {
  return request<OllamaModelsResponse>('/api/ollama/models', {
    query: { url },
    signal,
  })
}

/**
 * `GET /api/ollama/model-info` — one model's context window.
 *
 * The only place a context window is discovered rather than typed. Answers
 * 404 for a model the server does not have.
 */
export function readOllamaModelInfo(
  url: string,
  model: string,
  signal: AbortSignal,
): Promise<OllamaModelInfo> {
  return request<OllamaModelInfo>('/api/ollama/model-info', {
    query: { url, model },
    signal,
  })
}
