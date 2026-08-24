/**
 * One round's request, built from the record the flow has filled in.
 *
 * Three clicks send it -- the filters submit, "Show Me Another", and the
 * switch to discovery -- and all three send the same thing, which is why it is
 * built here rather than at each of them.
 */
import type { RecommendGenerateRequest } from '../../api/generated/types.gen.ts'
import type { AlbumFlow } from '../albumStore/albumStore.ts'

/** The body, or nothing where the flow has not reached the filters step. */
export function roundBody(
  flow: AlbumFlow,
): RecommendGenerateRequest | undefined {
  if (!flow.filters || !flow.answers) return undefined

  return {
    session_id: flow.sessionId,
    answers: [...flow.answers],
    answer_texts: [...(flow.answerTexts ?? [])],
    mode: flow.mode,
    genres: [...flow.filters.genres],
    decades: [...flow.filters.decades],
    familiarity_pref: flow.familiarity,
    max_albums: flow.filters.max_albums,
  }
}
