/**
 * Step two of the album flow: answer questions that sharpen the prompt.
 *
 * Every question is optional. The chosen option and the reader's own words
 * stay apart here, unlike the playlist flow, because the backend reads them
 * apart -- `libs/answerAlbumQuestions` says so.
 *
 * The answers are React state and reach the action through hidden inputs: a
 * pill toggle is not a form control, and its value has to be submitted.
 */
import { useState } from 'react'
import { Form, useLoaderData, useNavigate, useNavigation } from 'react-router'

import { Button } from '../../components/atoms/Button/Button.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { QuestionCard } from '../../components/molecules/QuestionCard/QuestionCard.tsx'
import { Stepper } from '../../components/molecules/Stepper/Stepper.tsx'
import type { AlbumFlow } from '../../libs/albumStore/albumStore.ts'
import { ALBUM_STEPS } from '../../libs/albumSteps/albumSteps.ts'
import styles from './AlbumRefine.module.scss'

/** What the reader gave for one question: an option, a detail, or neither. */
interface Answer {
  readonly option: string
  readonly detail: string
}

const BLANK: Answer = { option: '', detail: '' }

export function AlbumRefine() {
  const flow = useLoaderData<AlbumFlow>()
  const navigation = useNavigation()
  const navigate = useNavigate()
  const [answers, setAnswers] = useState<readonly Answer[]>(
    flow.questions.map(() => BLANK),
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
    <div className={styles.albumRefine}>
      <Stepper steps={ALBUM_STEPS} current={2} />

      <Heading level={2}>Just a couple questions</Heading>
      <Text tone="secondary">
        Help us narrow it down. Skip any you&apos;re not sure about.
      </Text>

      <Form method="post" className={styles.albumRefine__form}>
        <div className={styles.albumRefine__questions}>
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

        <div className={styles.albumRefine__actions}>
          <Button
            variant="secondary"
            disabled={working}
            onClick={() => {
              // Wrapped: the overload answers `void | Promise<void>`.
              Promise.resolve(navigate('/recommend')).catch(() => undefined)
            }}
          >
            Back
          </Button>
          <Button type="submit" variant="primary" disabled={working}>
            Next
          </Button>
        </div>
      </Form>
    </div>
  )
}
