/**
 * The album flow's endpoints, apart from the questions it shares.
 *
 * `POST /api/recommend/questions` is in `api/questions`: the playlist flow
 * asks it too (`frontend/app.js:2861`), so it does not belong here.
 *
 * Two of these spend nothing -- the preview counts rows in the cache, and
 * switching mode only re-keys a session. `analyze-prompt` spends one LLM call
 * but has no error path at all: a failure answers every filter
 * (`backend/api/routes/recommend/filters.py:24`).
 */
import type {
  AlbumPreviewResponse,
  AnalyzePromptFiltersRequest,
  FilterSuggestion,
  RecommendGenerateRequest,
  RecommendSwitchModeRequest,
  RecommendSwitchModeResponse,
} from '../generated/types.gen.ts'
import { request, stream } from '../request/request.ts'

/**
 * `POST /api/recommend/analyze-prompt` — which filters a prompt implies.
 *
 * The available names are sent with it: the backend suggests from what the
 * caller offers, so an empty list would come back empty.
 */
export function analyzeRecommendPrompt(
  body: AnalyzePromptFiltersRequest,
  signal: AbortSignal,
): Promise<FilterSuggestion> {
  return request<FilterSuggestion>('/api/recommend/analyze-prompt', {
    method: 'POST',
    body,
    signal,
  })
}

/**
 * `POST /api/recommend/switch-mode` — keep the answers, change the mode.
 *
 * Answers a new session id; the old one is deleted. 404 once the session has
 * expired, which is what sends the reader back to the start.
 */
export function switchRecommendMode(
  body: RecommendSwitchModeRequest,
  signal: AbortSignal,
): Promise<RecommendSwitchModeResponse> {
  return request<RecommendSwitchModeResponse>('/api/recommend/switch-mode', {
    method: 'POST',
    body,
    signal,
  })
}

/**
 * `GET /api/recommend/albums/preview` — how many albums a round would reach.
 *
 * Counts only. An unsynced library previews as zero rather than as an error.
 */
export function previewRecommendAlbums(
  query: {
    readonly genres?: string | undefined
    readonly decades?: string | undefined
    readonly max_albums: number
  },
  signal: AbortSignal,
): Promise<AlbumPreviewResponse> {
  return request<AlbumPreviewResponse>('/api/recommend/albums/preview', {
    query,
    signal,
  })
}

/**
 * `POST /api/recommend/generate` — one round, as a stream of frames.
 *
 * Returns the body unread. An expired session and an unusable library are
 * both statuses before the first frame, so the caller never reads either from
 * a frame. Narrowing the frames is `libs/albumFrames`.
 */
export function generateRecommendations(
  body: RecommendGenerateRequest,
  signal: AbortSignal,
): Promise<ReadableStream<Uint8Array>> {
  return stream('/api/recommend/generate', { method: 'POST', body, signal })
}
