/**
 * How many tracks a selection matches, and what sending them would cost.
 *
 * A resource route rather than a call from inside the page: the filters step
 * asks again on every click, and a fetcher keeps those reads off the
 * navigation entirely. `libs/loadStats` says more about why.
 *
 * A POST, so it is an action -- but it spends nothing. `POST /api/filter/preview`
 * counts rows in the local cache; the body is a filter selection, which is too
 * long and too structured to be a query string.
 */
import type { ActionFunctionArgs } from 'react-router'

import { previewFilters } from '../../api/analyze/analyze.ts'
import type {
  FilterPreviewRequest,
  FilterPreviewResponse,
} from '../../api/generated/types.gen.ts'
import { formLast, formText } from '../formText/formText.ts'

/** Named once: the route, the submit, and `shouldRevalidate` must agree. */
export const PREVIEW = '/playlist/filters/preview'

/**
 * `POST /playlist/filters/preview` — the count and the cost, or nothing.
 *
 * A failure answers nothing rather than faulting: the bar it fills is
 * informational, and the step stays usable without it.
 */
export async function previewSelection({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<FilterPreviewResponse | null> {
  const form = await request.formData()
  const selection: FilterPreviewRequest = {
    genres: form.getAll('genres').map(String),
    decades: form.getAll('decades').map(String),
    track_count: Number(formText(form, 'track_count')),
    exclude_live: formLast(form, 'exclude_live') === 'true',
    min_rating: Number(formText(form, 'min_rating')),
    max_tracks_to_ai: Number(formText(form, 'max_tracks_to_ai')),
  }

  try {
    return await previewFilters(selection, request.signal)
  } catch {
    return null
  }
}
