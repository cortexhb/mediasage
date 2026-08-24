/**
 * What a prompt implies, and what a filter selection would cost.
 *
 * `POST /api/analyze/prompt` spends two LLM calls and needs both Plex and a
 * model, so it is only ever reached from an action. `POST /api/filter/preview`
 * spends nothing once a sync has run -- it counts rows in the local cache.
 *
 * `/api/analyze/track` belongs to the seed flow and is not here yet.
 */
import type {
  AnalyzePromptRequest,
  AnalyzePromptResponse,
  FilterPreviewRequest,
  FilterPreviewResponse,
} from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/**
 * `POST /api/analyze/prompt` — the genres and decades a sentence implies.
 *
 * Answers the available choices as well as the suggested ones, so the filters
 * step needs no second read to draw the full list.
 */
export function analyzePrompt(
  prompt: AnalyzePromptRequest['prompt'],
  flowId: string,
  signal: AbortSignal,
): Promise<AnalyzePromptResponse> {
  return request<AnalyzePromptResponse>('/api/analyze/prompt', {
    method: 'POST',
    body: { prompt, flow_id: flowId } satisfies AnalyzePromptRequest,
    signal,
  })
}

/**
 * `POST /api/filter/preview` — how many tracks match, and what sending them costs.
 *
 * Answered from the local cache when a sync has run, which is why the filters
 * step can ask again on every change.
 */
export function previewFilters(
  filters: FilterPreviewRequest,
  signal: AbortSignal,
): Promise<FilterPreviewResponse> {
  return request<FilterPreviewResponse>('/api/filter/preview', {
    method: 'POST',
    body: filters,
    signal,
  })
}
