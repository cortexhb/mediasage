/**
 * Reading one saved result back, for `/result/:resultId`.
 *
 * A loader, not an action: the snapshot was paid for when it was generated and
 * reading it costs a database row. This is the whole reason the history feed's
 * entries are links.
 *
 * `frontend/app.js:604` rehydrated the live wizard from the same payload, so a
 * saved result arrived with buttons that had no session behind them. Here the
 * page is its own read-only route instead.
 */
import type { LoaderFunctionArgs } from 'react-router'

import { ApiError } from '../../api/request/request.ts'
import type { ResultDetail } from '../../api/results/results.ts'
import { readResult } from '../../api/results/results.ts'

/** What the reader is told, wording from `frontend/app.js:651`. */
const GONE = 'This result is no longer available.'

/**
 * The two answers that mean the result itself is the problem.
 *
 * 404 is deleted; 422 is a snapshot the models have outgrown
 * (`backend/api/routes/results/detail.py:26`). Both read the same to a reader.
 */
const MISSING = [404, 422]

export async function loadResult({
  params,
  request,
}: Pick<LoaderFunctionArgs, 'params' | 'request'>): Promise<ResultDetail> {
  const resultId = params.resultId
  if (!resultId) throw new Error(GONE)

  try {
    return await readResult(resultId, request.signal)
  } catch (error) {
    // Rewriting a 500 or a dead API would hide the failure.
    if (error instanceof ApiError && MISSING.includes(error.status)) {
      throw new Error(GONE, { cause: error })
    }
    throw error
  }
}
