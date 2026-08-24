/**
 * Step one of either flow: a box to describe what you want, and suggestions.
 *
 * Both flows ask for the same thing in the same shape -- a textarea, a row of
 * shuffled pills that fill it, one submit -- and differ only in their words
 * and in which set of suggestions they draw from.
 *
 * The textarea is uncontrolled: a long prompt would otherwise re-render the
 * page on every keystroke. A suggestion writes into it through the ref.
 *
 * Submitting is the caller's route action; this owns no request of its own.
 */
import { useRef, useState } from 'react'
import { Form, useNavigation } from 'react-router'

import type { SuggestionGroups } from '../../../libs/promptSuggestions/pickSuggestions.ts'
import {
  nextSuggestions,
  pickSuggestions,
} from '../../../libs/promptSuggestions/pickSuggestions.ts'
import { Button } from '../../atoms/Button/Button.tsx'
import { Heading } from '../../atoms/Heading/Heading.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import { Textarea } from '../../atoms/Textarea/Textarea.tsx'
import { Stepper } from '../Stepper/Stepper.tsx'
import { WorkingOverlay } from '../WorkingOverlay/WorkingOverlay.tsx'
import styles from './PromptForm.module.scss'

export interface PromptFormProps {
  readonly steps: readonly string[]
  readonly heading: string
  /** The line under the heading. */
  readonly blurb: string
  readonly placeholder: string
  /** Names the textarea for assistive technology. */
  readonly label: string
  readonly groups: SuggestionGroups
  readonly submitLabel: string
  /** What the action answered, where it answered a failure. */
  readonly error?: string | undefined
  /** Names the wait, and titles its overlay. */
  readonly waitLabel: string
  readonly stages: readonly string[]
}

export function PromptForm({
  steps,
  heading,
  blurb,
  placeholder,
  label,
  groups,
  submitLabel,
  error,
  waitLabel,
  stages,
}: PromptFormProps) {
  const box = useRef<HTMLTextAreaElement>(null)
  const [suggestions, setSuggestions] = useState(() => pickSuggestions(groups))
  const navigation = useNavigation()
  const working = navigation.state === 'submitting'

  /** Put a suggestion in the box, ready to be edited rather than sent. */
  const use = (suggestion: string): void => {
    const field = box.current
    if (!field) return
    field.value = suggestion
    field.focus()
  }

  return (
    <div className={styles.promptForm}>
      <Stepper steps={steps} current={1} />

      <Form method="post" className={styles.promptForm__form}>
        <Heading level={2}>{heading}</Heading>
        <Text tone="secondary">{blurb}</Text>

        <Textarea
          ref={box}
          name="prompt"
          rows={4}
          required
          disabled={working}
          placeholder={placeholder}
          aria-label={label}
        />

        {error !== undefined && (
          <Text tone="error" role="alert">
            {error}
          </Text>
        )}

        <div className={styles.promptForm__suggestions}>
          <div className={styles.promptForm__suggestionsHeader}>
            <Text tone="muted">Or try one of these</Text>
            {/* Not a `Button`: this one is a 32px circle, per the legacy. */}
            <button
              type="button"
              className={styles.promptForm__shuffle}
              onClick={() => {
                setSuggestions((shown) => nextSuggestions(groups, shown))
              }}
              aria-label="Show different suggestions"
              title="Show different suggestions"
            >
              ↻
            </button>
          </div>
          <div className={styles.promptForm__pills}>
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className={styles.promptForm__pill}
                onClick={() => {
                  use(suggestion)
                }}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.promptForm__actions}>
          <Button type="submit" variant="primary" disabled={working}>
            {submitLabel}
          </Button>
        </div>
      </Form>

      <WorkingOverlay open={working} label={waitLabel} steps={stages} titled />
    </div>
  )
}
