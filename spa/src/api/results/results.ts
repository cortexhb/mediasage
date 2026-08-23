/**
 * The saved-history endpoints, paired with their generated types.
 *
 * `GET /api/results` is the whole feed: one page at a time, newest first.
 * Reading one result back is Phase 4's `/result/:id`, so it is not here yet.
 */
import type { ResultListResponse } from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/**
 * `GET /api/results` — one page of history, newest first.
 *
 * `type` filters server-side and is left off entirely here: the feed's chips
 * filter a page already on screen, and asking again per chip would repaginate
 * under the reader.
 */
export function listResults(
  limit: number,
  offset: number,
  signal: AbortSignal,
): Promise<ResultListResponse> {
  return request<ResultListResponse>('/api/results', {
    query: { limit, offset },
    signal,
  })
}

/**
 * `DELETE /api/results/{result_id}` — forget one result.
 *
 * Answers 204, so there is nothing to return. A 404 means it was already
 * gone, which the feed treats as success.
 */
export function forgetResult(
  resultId: string,
  signal: AbortSignal,
): Promise<undefined> {
  return request<undefined>('/api/results/{result_id}', {
    method: 'DELETE',
    path: { result_id: resultId },
    signal,
  })
}
