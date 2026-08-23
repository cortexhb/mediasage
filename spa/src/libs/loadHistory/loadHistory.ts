/**
 * The first page of saved history, for Home.
 *
 * A failure answers an empty page rather than throwing. History is the bottom
 * third of Home; faulting the route would take the greeting and the three
 * create cards down with it, and those need no data at all.
 *
 * Read by `pages/Home`.
 */
import type { LoaderFunctionArgs } from 'react-router'

import type { ResultListItem } from '../../api/generated/types.gen.ts'
import { listResults } from '../../api/results/results.ts'

/** How many entries a page holds. `frontend/app.js:838` asked for the same. */
export const PAGE = 20

export interface HistoryPage {
  readonly items: readonly ResultListItem[]
  /** How many exist behind the page, which decides "Load more". */
  readonly total: number
  /** Whether the read failed, so the feed can say so instead of "empty". */
  readonly failed: boolean
}

/** Only `request` is read, so only that is asked for. */
export async function loadHistory({
  request,
}: Pick<LoaderFunctionArgs, 'request'>): Promise<HistoryPage> {
  try {
    const page = await listResults(PAGE, 0, request.signal)
    return { items: page.results ?? [], total: page.total ?? 0, failed: false }
  } catch {
    return { items: [], total: 0, failed: true }
  }
}
