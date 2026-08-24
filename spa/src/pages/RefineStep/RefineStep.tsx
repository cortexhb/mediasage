/**
 * Step two of the playlist flow: answer questions that sharpen the prompt.
 *
 * The step itself is `molecules/QuestionsStep`, shared with the album flow.
 * What is here is this flow's questions, its steps and where Back goes;
 * `libs/refinePrompt` is what reads the answers, joining an option and its
 * detail as `option (detail)` and sending null where neither was given
 * (`frontend/app.js:3073`).
 */
import { useActionData, useLoaderData } from 'react-router'

import { QuestionsStep } from '../../components/molecules/QuestionsStep/QuestionsStep.tsx'
import type { PromptFlow } from '../../libs/flowStore/flowStore.ts'
import { playlistSteps } from '../../libs/flowSteps/flowSteps.ts'
import type { RefineActionResult } from '../../libs/refinePrompt/refinePrompt.ts'

export function RefineStep() {
  const flow = useLoaderData<PromptFlow>()
  const result = useActionData<RefineActionResult>()

  return (
    <QuestionsStep
      steps={playlistSteps('prompt')}
      questions={flow.questions}
      backTo="/playlist/prompt"
      error={result?.error}
    />
  )
}
