/**
 * Step one of the prompt flow: describe the playlist.
 *
 * Asking for questions spends an LLM call and opens a server-held session, so
 * it is an action rather than a loader -- see `docs/migration.md`. What it
 * answers is carried to the refine step in the flow record.
 *
 * The form itself is `molecules/PromptForm`, which the album flow's first step
 * also draws; what is here is this flow's words and its suggestions.
 */
import { useActionData } from 'react-router'

import { PromptForm } from '../../components/molecules/PromptForm/PromptForm.tsx'
import type { PromptActionResult } from '../../libs/askPromptQuestions/askPromptQuestions.ts'
import { playlistSteps } from '../../libs/flowSteps/flowSteps.ts'
import { PROMPT_GROUPS } from '../../libs/promptSuggestions/promptSuggestions.ts'

const PLACEHOLDER = 'e.g., melancholy 90s alternative for a rainy day...'

/** The stages `frontend/app.js:2850` named for this same wait. */
const STAGES = [
  'Parsing your request...',
  'Crafting questions...',
  'Matching to your library...',
]

export function PromptStep() {
  const result = useActionData<PromptActionResult>()

  return (
    <PromptForm
      steps={playlistSteps('prompt')}
      heading="Describe your playlist"
      blurb="Tell us what kind of music you're in the mood for."
      placeholder={PLACEHOLDER}
      label="Playlist description"
      groups={PROMPT_GROUPS}
      submitLabel="Analyze"
      error={result?.error}
      waitLabel="Reading your prompt"
      stages={STAGES}
    />
  )
}
