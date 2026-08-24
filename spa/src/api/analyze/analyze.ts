/**
 * What a prompt implies, and what a filter selection would cost.
 *
 * `POST /api/analyze/prompt` and `POST /api/analyze/track` each spend LLM
 * calls and need both Plex and a model, so both are only ever reached from an
 * action. `POST /api/filter/preview` spends nothing once a sync has run -- it
 * counts rows in the local cache.
 */
import type {
  AnalyzePromptRequest,
  AnalyzePromptResponse,
  AnalyzeTrackRequest,
  AnalyzeTrackResponse,
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
 * `POST /api/analyze/track` — the dimensions a seed track can be explored along.
 *
 * Answers the track itself as well as its dimensions, so the step that draws
 * both needs no second read. 404 where the rating key names nothing.
 */
export function analyzeTrack(
  ratingKey: AnalyzeTrackRequest['rating_key'],
  flowId: string,
  signal: AbortSignal,
): Promise<AnalyzeTrackResponse> {
  return request<AnalyzeTrackResponse>('/api/analyze/track', {
    method: 'POST',
    body: {
      rating_key: ratingKey,
      flow_id: flowId,
    } satisfies AnalyzeTrackRequest,
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
