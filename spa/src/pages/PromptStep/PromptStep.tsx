/**
 * Step one of the prompt flow: describe the playlist.
 *
 * Asking for questions spends an LLM call and opens a server-held session, so
 * it is an action rather than a loader -- see `docs/migration.md`. What it
 * answers is carried to the refine step in the flow record.
 *
 * The textarea is uncontrolled: a long prompt would otherwise re-render the
 * page on every keystroke. A suggestion writes into it through the ref.
 */
import { useRef, useState } from 'react'
import { Form, useActionData, useNavigation } from 'react-router'

import { Button } from '../../components/atoms/Button/Button.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Overlay } from '../../components/atoms/Overlay/Overlay.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { Textarea } from '../../components/atoms/Textarea/Textarea.tsx'
import { StepProgress } from '../../components/molecules/StepProgress/StepProgress.tsx'
import { Stepper } from '../../components/molecules/Stepper/Stepper.tsx'
import type { PromptActionResult } from '../../libs/askPromptQuestions/askPromptQuestions.ts'
import { playlistSteps } from '../../libs/playlistSteps/playlistSteps.ts'
import {
  nextSuggestions,
  pickSuggestions,
} from '../../libs/promptSuggestions/pickSuggestions.ts'
import { PROMPT_GROUPS } from '../../libs/promptSuggestions/promptSuggestions.ts'
import styles from './PromptStep.module.scss'

const PLACEHOLDER = 'e.g., melancholy 90s alternative for a rainy day...'

/** The stages `frontend/app.js:2850` named for this same wait. */
const STAGES = [
  'Parsing your request...',
  'Crafting questions...',
  'Matching to your library...',
]

export function PromptStep() {
  const box = useRef<HTMLTextAreaElement>(null)
  const [suggestions, setSuggestions] = useState(() =>
    pickSuggestions(PROMPT_GROUPS),
  )
  const [watching, setWatching] = useState(true)
  const navigation = useNavigation()
  const result = useActionData<PromptActionResult>()
  const analysing = navigation.state === 'submitting'

  /** Put a suggestion in the box, ready to be edited rather than sent. */
  const use = (suggestion: string): void => {
    const field = box.current
    if (!field) return
    field.value = suggestion
    field.focus()
  }

  return (
    <div className={styles.prompt}>
      <Stepper steps={playlistSteps('prompt')} current={1} />

      <Form
        method="post"
        className={styles.prompt__form}
        onSubmit={() => {
          // Dismissed once, shown again for the next submit.
          setWatching(true)
        }}
      >
        <Heading level={2}>Describe your playlist</Heading>
        <Text tone="secondary">
          Tell us what kind of music you&apos;re in the mood for.
        </Text>

        <Textarea
          ref={box}
          name="prompt"
          rows={4}
          required
          disabled={analysing}
          placeholder={PLACEHOLDER}
          aria-label="Playlist description"
        />

        {result && (
          <Text tone="error" role="alert">
            {result.error}
          </Text>
        )}

        <div className={styles.prompt__suggestions}>
          <div className={styles.prompt__suggestionsHeader}>
            <Text tone="muted">Or try one of these</Text>
            {/* Not a `Button`: this one is a 32px circle, per the legacy. */}
            <button
              type="button"
              className={styles.prompt__shuffle}
              onClick={() => {
                setSuggestions((shown) => nextSuggestions(PROMPT_GROUPS, shown))
              }}
              aria-label="Show different suggestions"
              title="Show different suggestions"
            >
              ↻
            </button>
          </div>
          <div className={styles.prompt__pills}>
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className={styles.prompt__pill}
                onClick={() => {
                  use(suggestion)
                }}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.prompt__actions}>
          <Button type="submit" variant="primary" disabled={analysing}>
            Analyze
          </Button>
        </div>
      </Form>

      {/* Dismissable: closing it abandons the wait, not the request. */}
      <Overlay
        open={analysing && watching}
        onClose={() => {
          setWatching(false)
        }}
        label="Reading your prompt"
      >
        <div className={styles.prompt__working}>
          <Heading level={2}>Reading your prompt</Heading>
          <StepProgress steps={STAGES} />
        </div>
      </Overlay>
    </div>
  )
}
