/**
 * Step two of the album flow: answer questions that sharpen the prompt.
 *
 * The step itself is `molecules/QuestionsStep`, shared with the playlist flow.
 * The chosen option and the reader's own words stay apart once submitted,
 * unlike the playlist flow, because the backend reads them apart --
 * `libs/answerAlbumQuestions` says so.
 */
import { useLoaderData } from 'react-router'

import { QuestionsStep } from '../../components/molecules/QuestionsStep/QuestionsStep.tsx'
import type { AlbumFlow } from '../../libs/albumStore/albumStore.ts'
import { ALBUM_STEPS } from '../../libs/flowSteps/flowSteps.ts'

export function AlbumRefine() {
  const flow = useLoaderData<AlbumFlow>()

  return (
    <QuestionsStep
      steps={ALBUM_STEPS}
      questions={flow.questions}
      backTo="/recommend"
    />
  )
}
