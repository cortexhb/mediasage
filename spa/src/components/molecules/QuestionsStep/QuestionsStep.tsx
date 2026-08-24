/**
 * Step two of either flow: answer questions that sharpen the prompt.
 *
 * Every question is optional, and both flows submit the same fields --
 * `option-<n>` and `detail-<n>`, positional. What each flow does with them
 * differs (`libs/refinePrompt` joins them as `option (detail)`,
 * `libs/answerAlbumQuestions` keeps them apart), and that is the action's
 * business rather than this one's.
 *
 * The answers are React state and reach the action through hidden inputs: a
 * pill toggle is not a form control, and its value has to be submitted.
 */
import { useState } from 'react'
import { Form, useNavigation } from 'react-router'

import type { ClarifyingQuestion } from '../../../api/generated/types.gen.ts'
import { useGo } from '../../../libs/useGo/useGo.ts'
import { Button } from '../../atoms/Button/Button.tsx'
import { Heading } from '../../atoms/Heading/Heading.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import { QuestionCard } from '../QuestionCard/QuestionCard.tsx'
import { Stepper } from '../Stepper/Stepper.tsx'
import { WorkingOverlay } from '../WorkingOverlay/WorkingOverlay.tsx'
import styles from './QuestionsStep.module.scss'

/**
 * The one stage this wait has, named as `frontend/app.js:2853` named it.
 *
 * `frontend/app.js:4244` awaited the album flow's filter analysis behind a
 * live page and showed nothing, so the reader met a dead button.
 */
const STAGES = ['Matching to your library...']

/** What the reader gave for one question: an option, a detail, or neither. */
interface Answer {
  readonly option: string
  readonly detail: string
}

const BLANK: Answer = { option: '', detail: '' }

export interface QuestionsStepProps {
  readonly steps: readonly string[]
  readonly questions: readonly ClarifyingQuestion[]
  /** Where Back goes: step one of the flow that asked. */
  readonly backTo: string
  /** What the action answered, where it answered a failure. */
  readonly error?: string | undefined
}

export function QuestionsStep({
  steps,
  questions,
  backTo,
  error,
}: QuestionsStepProps) {
  const navigation = useNavigation()
  const go = useGo()
  const [answers, setAnswers] = useState<readonly Answer[]>(
    questions.map(() => BLANK),
  )
  const working = navigation.state === 'submitting'

  /**
   * Replace one answer, leaving the others as they were.
   *
   * Functional, because skipping calls this twice in one handler and the
   * second call would otherwise overwrite the first from stale state.
   */
  const change = (index: number, next: (was: Answer) => Answer): void => {
    setAnswers((was) =>
      was.map((each, at) => (at === index ? next(each) : each)),
    )
  }

  return (
    <div className={styles.questionsStep}>
      <Stepper steps={steps} current={2} />

      <Heading level={2}>Just a couple questions</Heading>
      <Text tone="secondary">
        Help us narrow it down. Skip any you&apos;re not sure about.
      </Text>

      <Form method="post" className={styles.questionsStep__form}>
        <div className={styles.questionsStep__questions}>
          {questions.map((question, index) => {
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
                    change(index, (was) => ({ ...was, option }))
                  }}
                  onDetail={(detail) => {
                    change(index, (was) => ({ ...was, detail }))
                  }}
                />
              </div>
            )
          })}
        </div>

        {error !== undefined && (
          <Text tone="error" role="alert">
            {error}
          </Text>
        )}

        <div className={styles.questionsStep__actions}>
          <Button
            variant="secondary"
            disabled={working}
            onClick={() => {
              go(backTo)
            }}
          >
            Back
          </Button>
          <Button type="submit" variant="primary" disabled={working}>
            Next
          </Button>
        </div>
      </Form>

      <WorkingOverlay
        open={working}
        label="Matching to your library"
        steps={STAGES}
        titled
      />
    </div>
  )
}
