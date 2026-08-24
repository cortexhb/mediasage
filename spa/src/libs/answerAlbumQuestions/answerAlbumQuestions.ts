/**
 * What leaving the album refine step does: keep the answers, collect the
 * suggestion.
 *
 * The answers stay in two lists, not one: `frontend/app.js:4423` sends the
 * chosen option as `answers` and the reader's own words as `answer_texts`,
 * and the backend reads them apart. The playlist flow joins them instead --
 * that is its shape, not this one's.
 *
 * The suggestion is awaited here, as `handleRefineNext` awaited it
 * (`frontend/app.js:4247`), so the filters step opens with the answer already
 * in the record. A failure is not an error: the step then preselects
 * everything and says nothing about a suggestion.
 */
import type { ActionFunctionArgs } from 'react-router'
import { redirect } from 'react-router'

import { readAlbumFlow, writeAlbumFlow } from '../albumStore/albumStore.ts'
import { formText } from '../formText/formText.ts'
import { collectSuggestion } from '../suggestionCache/suggestionCache.ts'

export async function answerAlbumQuestions({
  request,
}: Pick<ActionFunctionArgs, 'request'>): Promise<Response> {
  const flow = readAlbumFlow()
  if (!flow) return redirect('/recommend')

  const form = await request.formData()
  const answers = flow.questions.map(
    (_, index) => formText(form, `option-${String(index)}`) || null,
  )
  const answerTexts = flow.questions.map((_, index) =>
    formText(form, `detail-${String(index)}`).trim(),
  )

  // Already in the record where it landed while the reader was answering.
  const suggested =
    flow.suggested ??
    (await collectSuggestion(flow.prompt)?.catch(() => undefined))

  writeAlbumFlow({ ...flow, answers, answerTexts, suggested })
  return redirect('/recommend/filters')
}
