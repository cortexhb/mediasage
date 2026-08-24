/**
 * Step one of the album flow: describe the record you want.
 *
 * Asking for questions spends two LLM calls and opens the server-held session
 * the rest of the flow is addressed by, so it is an action rather than a
 * loader. The filter analysis is fired alongside it and collected two steps
 * later -- `libs/suggestionCache`.
 *
 * The textarea is uncontrolled, and a suggestion writes into it through the
 * ref, for the reason `pages/PromptStep` gives.
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
import { ALBUM_PROMPT_GROUPS } from '../../libs/albumSuggestions/albumSuggestions.ts'
import { ALBUM_STEPS } from '../../libs/albumSteps/albumSteps.ts'
import type { AlbumPromptResult } from '../../libs/askAlbumQuestions/askAlbumQuestions.ts'
import {
  nextSuggestions,
  pickSuggestions,
} from '../../libs/promptSuggestions/pickSuggestions.ts'
import styles from './AlbumPrompt.module.scss'

const PLACEHOLDER = 'e.g., something for a rainy Sunday morning...'

/** The stages `frontend/app.js:4209` named for this same wait. */
const STAGES = ['Analyzing your request...', 'Crafting questions...']

export function AlbumPrompt() {
  const box = useRef<HTMLTextAreaElement>(null)
  const [suggestions, setSuggestions] = useState(() =>
    pickSuggestions(ALBUM_PROMPT_GROUPS),
  )
  const [watching, setWatching] = useState(true)
  const navigation = useNavigation()
  const result = useActionData<AlbumPromptResult>()
  const asking = navigation.state === 'submitting'

  /** Put a suggestion in the box, ready to be edited rather than sent. */
  const use = (suggestion: string): void => {
    const field = box.current
    if (!field) return
    field.value = suggestion
    field.focus()
  }

  return (
    <div className={styles.albumPrompt}>
      <Stepper steps={ALBUM_STEPS} current={1} />

      <Form
        method="post"
        className={styles.albumPrompt__form}
        onSubmit={() => {
          // Dismissed once, shown again for the next submit.
          setWatching(true)
        }}
      >
        <Heading level={2}>What are you in the mood for?</Heading>
        <Text tone="secondary">
          Describe the vibe, moment, or feeling you want an album for.
        </Text>

        <Textarea
          ref={box}
          name="prompt"
          rows={4}
          required
          disabled={asking}
          placeholder={PLACEHOLDER}
          aria-label="Album recommendation prompt"
        />

        {result && (
          <Text tone="error" role="alert">
            {result.error}
          </Text>
        )}

        <div className={styles.albumPrompt__suggestions}>
          <div className={styles.albumPrompt__suggestionsHeader}>
            <Text tone="muted">Or try one of these</Text>
            {/* Not a `Button`: this one is a 32px circle, per the legacy. */}
            <button
              type="button"
              className={styles.albumPrompt__shuffle}
              onClick={() => {
                setSuggestions((shown) =>
                  nextSuggestions(ALBUM_PROMPT_GROUPS, shown),
                )
              }}
              aria-label="Show different suggestions"
              title="Show different suggestions"
            >
              ↻
            </button>
          </div>
          <div className={styles.albumPrompt__pills}>
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className={styles.albumPrompt__pill}
                onClick={() => {
                  use(suggestion)
                }}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.albumPrompt__actions}>
          <Button type="submit" variant="primary" disabled={asking}>
            Next
          </Button>
        </div>
      </Form>

      {/* Dismissable: closing it abandons the wait, not the request. */}
      <Overlay
        open={asking && watching}
        onClose={() => {
          setWatching(false)
        }}
        label="Analyzing your request"
      >
        <div className={styles.albumPrompt__working}>
          <Heading level={2}>Analyzing your request</Heading>
          <StepProgress steps={STAGES} />
        </div>
      </Overlay>
    </div>
  )
}
