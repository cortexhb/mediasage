/**
 * Step two of the playlist flow: answer questions that sharpen the prompt.
 *
 * Every question is optional. `frontend/app.js:3073` joins an option and its
 * detail as `option (detail)` and sends null where neither was given, so a
 * skipped question costs the reader nothing; `libs/refinePrompt` keeps that.
 *
 * The answers are React state and reach the action through hidden inputs: a
 * pill toggle is not a form control, and its value has to be submitted.
 */
import { useState } from 'react'
import {
  Form,
  useActionData,
  useLoaderData,
  useNavigate,
  useNavigation,
} from 'react-router'

import { Button } from '../../components/atoms/Button/Button.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Overlay } from '../../components/atoms/Overlay/Overlay.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { QuestionCard } from '../../components/molecules/QuestionCard/QuestionCard.tsx'
import { StepProgress } from '../../components/molecules/StepProgress/StepProgress.tsx'
import { Stepper } from '../../components/molecules/Stepper/Stepper.tsx'
import type { PlaylistFlow } from '../../libs/flowStore/flowStore.ts'
import { PLAYLIST_STEPS } from '../../libs/playlistSteps/playlistSteps.ts'
import type { RefineActionResult } from '../../libs/refinePrompt/refinePrompt.ts'
import styles from './RefineStep.module.scss'

/** The one stage this wait has, named as `frontend/app.js:2853` named it. */
const STAGES = ['Matching to your library...']

/** What the reader gave for one question: an option, a detail, or neither. */
interface Answer {
  readonly option: string
  readonly detail: string
}

const BLANK: Answer = { option: '', detail: '' }

export function RefineStep() {
  const flow = useLoaderData<PlaylistFlow>()
  const result = useActionData<RefineActionResult>()
  const navigation = useNavigation()
  const navigate = useNavigate()
  const [answers, setAnswers] = useState<readonly Answer[]>(
    flow.questions.map(() => BLANK),
  )
  const [watching, setWatching] = useState(true)
  const working = navigation.state === 'submitting'

  /** Replace one answer, leaving the others as they were. */
  const change = (index: number, next: Answer): void => {
    setAnswers(answers.map((each, at) => (at === index ? next : each)))
  }

  return (
    <div className={styles.refine}>
      <Stepper steps={PLAYLIST_STEPS} current={2} />

      <Heading level={2}>Just a couple questions</Heading>
      <Text tone="secondary">
        Help us narrow it down. Skip any you&apos;re not sure about.
      </Text>

      <Form
        method="post"
        className={styles.refine__form}
        onSubmit={() => {
          setWatching(true)
        }}
      >
        <div className={styles.refine__questions}>
          {flow.questions.map((question, index) => {
            const answer = answers[index] ?? BLANK
            return (
              <div key={question.question_text}>
                <input
                  type="hidden"
                  name={`option-${String(index)}`}
                  value={answer.option}
                />
                <QuestionCard
                  question={question.question_text}
                  options={question.options}
                  name={`detail-${String(index)}`}
                  answer={answer.option}
                  detail={answer.detail}
                  onAnswer={(option) => {
                    change(index, { ...answer, option })
                  }}
                  onDetail={(detail) => {
                    change(index, { ...answer, detail })
                  }}
                />
              </div>
            )
          })}
        </div>

        {result && (
          <Text tone="error" role="alert">
            {result.error}
          </Text>
        )}

        <div className={styles.refine__actions}>
          <Button
            variant="secondary"
            disabled={working}
            onClick={() => {
              // Wrapped: the overload answers `void | Promise<void>`.
              Promise.resolve(navigate('/playlist/prompt')).catch(
                () => undefined,
              )
            }}
          >
            Back
          </Button>
          <Button type="submit" variant="primary" disabled={working}>
            Next
          </Button>
        </div>
      </Form>

      {/* Dismissable: closing it abandons the wait, not the request. */}
      <Overlay
        open={working && watching}
        onClose={() => {
          setWatching(false)
        }}
        label="Matching to your library"
      >
        <div className={styles.refine__working}>
          <Heading level={2}>Matching to your library</Heading>
          <StepProgress steps={STAGES} />
        </div>
      </Overlay>
    </div>
  )
}
