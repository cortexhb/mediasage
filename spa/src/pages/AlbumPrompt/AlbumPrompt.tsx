/**
 * Step one of the album flow: describe the record you want.
 *
 * Asking for questions spends two LLM calls and opens the server-held session
 * the rest of the flow is addressed by, so it is an action rather than a
 * loader. The filter analysis is fired alongside it and collected two steps
 * later -- `libs/suggestionCache`.
 *
 * The form itself is `molecules/PromptForm`, shared with `pages/PromptStep`.
 */
import { useActionData } from 'react-router'

import { PromptForm } from '../../components/molecules/PromptForm/PromptForm.tsx'
import { ALBUM_PROMPT_GROUPS } from '../../libs/albumSuggestions/albumSuggestions.ts'
import type { AlbumPromptResult } from '../../libs/askAlbumQuestions/askAlbumQuestions.ts'
import { ALBUM_STEPS } from '../../libs/flowSteps/flowSteps.ts'

const PLACEHOLDER = 'e.g., something for a rainy Sunday morning...'

/** The stages `frontend/app.js:4209` named for this same wait. */
const STAGES = ['Analyzing your request...', 'Crafting questions...']

export function AlbumPrompt() {
  const result = useActionData<AlbumPromptResult>()

  return (
    <PromptForm
      steps={ALBUM_STEPS}
      heading="What are you in the mood for?"
      blurb="Describe the vibe, moment, or feeling you want an album for."
      placeholder={PLACEHOLDER}
      label="Album recommendation prompt"
      groups={ALBUM_PROMPT_GROUPS}
      submitLabel="Next"
      error={result?.error}
      waitLabel="Analyzing your request"
      stages={STAGES}
    />
  )
}
