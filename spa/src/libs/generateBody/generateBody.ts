/**
 * The generate request, from what the earlier steps left behind.
 *
 * The filters were already narrowed when they were chosen -- all-selected is
 * stored as `[]`, per `frontend/app.js:3061` -- so this only reshapes.
 * `refinement_answers` is positional and carries null for a skipped question,
 * which is why it is passed through rather than filtered.
 *
 * The two modes differ in one half of the body, as `app.js:3070` had it: a
 * prompt flow sends the sentence and the answers, a seed flow sends the track
 * and the dimensions to explore.
 */
import type { GenerateRequest } from '../../api/generated/types.gen.ts'
import type { ChosenFilters, PlaylistFlow } from '../flowStore/flowStore.ts'

export function generateBody(
  flow: PlaylistFlow,
  filters: ChosenFilters,
): GenerateRequest {
  return {
    flow_id: flow.id,
    ...asked(flow),
    genres: [...filters.genres],
    decades: [...filters.decades],
    track_count: filters.track_count,
    exclude_live: filters.exclude_live,
    min_rating: filters.min_rating,
    max_tracks_to_ai: filters.max_tracks_to_ai,
  }
}

/** The half of the body that says what this flow is asking for. */
function asked(flow: PlaylistFlow): Partial<GenerateRequest> {
  if (flow.mode === 'prompt') {
    return {
      prompt: flow.prompt,
      ...(flow.refinementAnswers?.length
        ? { refinement_answers: [...flow.refinementAnswers] }
        : {}),
    }
  }

  return {
    seed_track: {
      rating_key: flow.track.rating_key,
      selected_dimensions: [...(flow.selectedDimensions ?? [])],
    },
    ...(flow.notes ? { additional_notes: flow.notes } : {}),
  }
}
