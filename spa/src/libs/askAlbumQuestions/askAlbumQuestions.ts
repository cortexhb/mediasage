/**
 * What submitting the album prompt does: ask for questions, open the session.
 *
 * An action rather than a loader because it spends two LLM calls and creates
 * the server-held session the rest of the flow is addressed by. The filter
 * analysis is started here and not awaited -- `libs/suggestionCache` says why.
 *
 * The mode starts at `library`, as `frontend/app.js:73` starts it; the
 * familiarity is whatever the reader last chose, on any flow.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { askQuestions } from '../../api/questions/questions.ts'
import { writeAlbumFlow } from '../albumStore/albumStore.ts'
import { explainError } from '../explainError/explainError.ts'
import { readFamiliarity } from '../familiarityPref/familiarityPref.ts'
import { newFlowId } from '../flowId/flowId.ts'
import { formText } from '../formText/formText.ts'
import {
  keepSuggestion,
  startSuggestion,
} from '../suggestionCache/suggestionCache.ts'

/** What the album prompt step renders when the request failed. */
export interface AlbumPromptResult {
  readonly error: string
}

export async function askAlbumQuestions({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<Response | AlbumPromptResult> {
  const form = await request.formData()
  const prompt = formText(form, 'prompt').trim()
  if (!prompt) return { error: 'Please enter a prompt' }

  // Minted here, before the first call: everything this flow spends is traced
  // under it.
  const id = newFlowId()
  startSuggestion(prompt)

  try {
    const asked = await askQuestions(prompt, id, request.signal)
    writeAlbumFlow({
      id,
      sessionId: asked.session_id,
      prompt,
      questions: asked.questions,
      mode: 'library',
      familiarity: readFamiliarity(),
    })
    // After the write: a suggestion that landed first would be overwritten.
    keepSuggestion(prompt)
  } catch (error) {
    return { error: explainError(error) }
  }

  return redirect('/recommend/refine')
}
