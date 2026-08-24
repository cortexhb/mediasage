/**
 * The saved-history endpoints, paired with their generated types.
 *
 * `GET /api/results` is the whole feed: one page at a time, newest first.
 * `GET /api/results/{id}` is one of them, with the snapshot to redraw it from.
 */
import type {
  AlbumResultDetail,
  PlaylistResultDetail,
  ResultListResponse,
} from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/** Either shape the detail endpoint answers, told apart by `type`. */
export type ResultDetail = PlaylistResultDetail | AlbumResultDetail

/**
 * `GET /api/results/{result_id}` — one saved result and its snapshot.
 *
 * 422 is its own case: `backend/api/routes/results/detail.py:26` answers it
 * for a snapshot too old for the current models, which is not a missing one.
 */
export function readResult(
  resultId: string,
  signal: AbortSignal,
): Promise<ResultDetail> {
  return request<ResultDetail>('/api/results/{result_id}', {
    path: { result_id: resultId },
    signal,
  })
}

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
