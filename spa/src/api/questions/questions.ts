/**
 * The clarifying questions a prompt earns, before anything is generated.
 *
 * `POST /api/recommend/questions` is named for the album flow but serves both:
 * `frontend/app.js:2861` calls it from the playlist flow too, and the answers
 * come back as `refinement_answers` on the generate request.
 *
 * It spends an LLM call and opens a server-held session, so it is only ever
 * reached from an action.
 */
import type {
  RecommendQuestionsRequest,
  RecommendQuestionsResponse,
} from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/** `POST /api/recommend/questions` — questions, and the session holding them. */
export function askQuestions(
  prompt: RecommendQuestionsRequest['prompt'],
  flowId: string,
  signal: AbortSignal,
): Promise<RecommendQuestionsResponse> {
  return request<RecommendQuestionsResponse>('/api/recommend/questions', {
    method: 'POST',
    body: { prompt, flow_id: flowId } satisfies RecommendQuestionsRequest,
    signal,
  })
}
