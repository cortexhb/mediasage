/**
 * What submitting the prompt does: ask for questions, start the analysis.
 *
 * An action rather than a loader because it spends an LLM call and opens a
 * server-held session. The analysis is started here and not awaited --
 * `libs/analysisCache` says why -- so its seconds are spent while the reader
 * answers rather than in front of a spinner.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { askQuestions } from '../../api/questions/questions.ts'
import { keepAnalysis, startAnalysis } from '../analysisCache/analysisCache.ts'
import { explainError } from '../explainError/explainError.ts'
import { formText } from '../formText/formText.ts'
import { newFlowId, writePlaylistFlow } from '../flowStore/flowStore.ts'

/** What the prompt step renders when the request failed. */
export interface PromptActionResult {
  readonly error: string
}

export async function askPromptQuestions({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<
  Response | PromptActionResult
> {
  const form = await request.formData()
  const prompt = formText(form, 'prompt').trim()
  if (!prompt) return { error: 'Describe the playlist you want first.' }

  // Minted here, before the first call: everything this flow spends is traced
  // under it.
  const id = newFlowId()
  startAnalysis(prompt, id)

  try {
    const asked = await askQuestions(prompt, id, request.signal)
    writePlaylistFlow({ id, prompt, questions: asked.questions })
    // After the write: an analysis that landed first would be overwritten.
    keepAnalysis(prompt)
  } catch (error) {
    return { error: explainError(error) }
  }

  return redirect('/playlist/prompt/refine')
}
