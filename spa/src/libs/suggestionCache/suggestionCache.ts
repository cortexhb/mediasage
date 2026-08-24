/**
 * The filter suggestion, started early and kept once it lands.
 *
 * `frontend/app.js:4213` fires `POST /api/recommend/analyze-prompt` alongside
 * the questions and awaits it only when the reader leaves the refine step, so
 * its seconds are spent while they are answering. This holds that promise,
 * which is what `state.rec.filterAnalysisPromise` was.
 *
 * The available names have to be read before the analysis can be asked for --
 * the backend suggests from the list it is given. That read is part of the
 * background work here rather than a step the reader waits through.
 *
 * A failure is not an error anywhere: the endpoint has none
 * (`backend/api/routes/recommend/filters.py:24`), and a read that fails leaves
 * the filters step with nothing preselected, which is where it starts anyway.
 */
import type { FilterSuggestion } from '../../api/generated/types.gen.ts'
import { readLibraryStats } from '../../api/library/library.ts'
import { analyzeRecommendPrompt } from '../../api/recommend/recommend.ts'
import { readAlbumFlow, writeAlbumFlow } from '../albumStore/albumStore.ts'

interface Held {
  readonly prompt: string
  readonly suggestion: Promise<FilterSuggestion>
}

let held: Held | undefined

/** The names the analysis chooses from, then what it chose. */
async function suggested(
  prompt: string,
  signal: AbortSignal,
): Promise<FilterSuggestion> {
  const { genres, decades } = await readLibraryStats(signal)
  return analyzeRecommendPrompt(
    {
      prompt,
      genres: genres.map((genre) => genre.name),
      decades: decades.map((decade) => decade.name),
    },
    signal,
  )
}

/**
 * Start analysing, and answer nothing. The result is collected later.
 *
 * Its own signal, not the action's: react-router aborts a navigation's
 * request once that navigation is done, and this outlives it by design.
 */
export function startSuggestion(prompt: string): void {
  const suggestion = suggested(prompt, new AbortController().signal)
  // Attached now, so a failure before `collect` is not an unhandled rejection.
  suggestion.catch(() => undefined)
  held = { prompt, suggestion }
}

/**
 * Write the suggestion into the flow record once it lands.
 *
 * Called after the record exists, never before: the two requests race, and a
 * write from here that beat the questions would be overwritten by them.
 */
export function keepSuggestion(prompt: string): void {
  const started = collectSuggestion(prompt)
  if (!started) return

  void started
    .then((suggestion) => {
      const flow = readAlbumFlow()
      // A newer prompt owns the record by now.
      if (flow?.prompt !== prompt) return
      writeAlbumFlow({ ...flow, suggested: suggestion })
    })
    .catch(() => undefined)
}

/** The suggestion started for this prompt, if one was and it is still held. */
export function collectSuggestion(
  prompt: string,
): Promise<FilterSuggestion> | undefined {
  return held?.prompt === prompt ? held.suggestion : undefined
}

/** Drop what is held, once its flow has been started over. */
export function forgetSuggestion(): void {
  held = undefined
}
