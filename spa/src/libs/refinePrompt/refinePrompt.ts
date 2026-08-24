/**
 * What leaving the refine step does: keep the answers, collect the analysis.
 *
 * The answers are positional, one per question, and null where the reader
 * skipped -- `backend` reads them alongside the questions it still holds.
 * `frontend/app.js:3073` joins an option and its detail as `option (detail)`,
 * and this keeps that shape so the prompt the model sees does not change.
 *
 * An action because the analysis it collects spends two LLM calls, even
 * though on the common path it was already paid for by the prompt step.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { analyzePrompt } from '../../api/analyze/analyze.ts'
import { collectAnalysis } from '../analysisCache/analysisCache.ts'
import { explainError } from '../explainError/explainError.ts'
import { readPlaylistFlow, writePlaylistFlow } from '../flowStore/flowStore.ts'
import { formText } from '../formText/formText.ts'

/** What the refine step renders when the analysis failed. */
export interface RefineActionResult {
  readonly error: string
}

/** One answer, as the backend reads it: option, detail, both, or neither. */
function answerOf(option: string, detail: string): string | null {
  if (option && detail) return `${option} (${detail})`
  return option || detail || null
}

export async function refinePrompt({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<
  Response | RefineActionResult
> {
  const flow = readPlaylistFlow()
  if (!flow) return redirect('/playlist/prompt')

  const form = await request.formData()
  const refinementAnswers = flow.questions.map((_, index) =>
    answerOf(
      formText(form, `option-${String(index)}`),
      formText(form, `detail-${String(index)}`).trim(),
    ),
  )

  try {
    // Started by the prompt step; asked again only where that was lost.
    const analysis = await (collectAnalysis(flow.prompt) ??
      analyzePrompt(flow.prompt, flow.id, request.signal))
    writePlaylistFlow({ ...flow, refinementAnswers, analysis })
  } catch (error) {
    return { error: explainError(error) }
  }

  return redirect('/playlist/prompt/filters')
}
