/**
 * One clarifying question: its options, a free-text detail, and a skip.
 *
 * Ports `.question-card` from `frontend/app.js:4266`. An option is a toggle
 * rather than a radio -- clicking the chosen one clears it, which is how the
 * legacy behaved and is the only way to unanswer without skipping.
 *
 * The answer and the detail are separate: `frontend/app.js:3073` joins them as
 * `option (detail)`, and either alone is a valid answer.
 */
import { useId } from 'react'

import { Input } from '../../atoms/Input/Input.tsx'
import styles from './QuestionCard.module.scss'

export interface QuestionCardProps {
  readonly question: string
  readonly options: readonly string[]
  /** Empty where the question is unanswered or skipped. */
  readonly answer: string
  readonly detail: string
  /** Form field name for the detail, which is submitted with the answers. */
  readonly name: string
  readonly onAnswer: (answer: string) => void
  readonly onDetail: (detail: string) => void
}

export function QuestionCard({
  question,
  options,
  answer,
  detail,
  name,
  onAnswer,
  onDetail,
}: QuestionCardProps) {
  const labelled = useId()

  return (
    <div className={styles.questionCard}>
      <p className={styles.questionCard__question} id={labelled}>
        {question}
      </p>

      <div
        className={styles.questionCard__options}
        role="group"
        aria-labelledby={labelled}
      >
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className={styles.questionCard__option}
            aria-pressed={answer === option}
            onClick={() => {
              onAnswer(answer === option ? '' : option)
            }}
          >
            {option}
          </button>
        ))}
      </div>

      <Input
        name={name}
        value={detail}
        placeholder="Add your own detail (optional)"
        aria-label={`Your own detail for: ${question}`}
        onChange={(event) => {
          onDetail(event.target.value)
        }}
      />

      <button
        type="button"
        className={styles.questionCard__skip}
        onClick={() => {
          onAnswer('')
          onDetail('')
        }}
      >
        Skip this question
      </button>
    </div>
  )
}
