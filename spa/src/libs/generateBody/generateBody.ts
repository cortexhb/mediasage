/**
 * The generate request, from what the earlier steps left behind.
 *
 * The filters were already narrowed when they were chosen -- all-selected is
 * stored as `[]`, per `frontend/app.js:3061` -- so this only reshapes.
 * `refinement_answers` is positional and carries null for a skipped question,
 * which is why it is passed through rather than filtered.
 */
import type { GenerateRequest } from '../../api/generated/types.gen.ts'
import type { ChosenFilters } from '../flowStore/flowStore.ts'

export function generateBody(
  flowId: string,
  prompt: string,
  answers: readonly (string | null)[] | undefined,
  filters: ChosenFilters,
): GenerateRequest {
  return {
    flow_id: flowId,
    prompt,
    ...(answers?.length ? { refinement_answers: [...answers] } : {}),
    genres: [...filters.genres],
    decades: [...filters.decades],
    track_count: filters.track_count,
    exclude_live: filters.exclude_live,
    min_rating: filters.min_rating,
    max_tracks_to_ai: filters.max_tracks_to_ai,
  }
}
