/**
 * The prompt analysis, started early and kept once it lands.
 *
 * `frontend/app.js:2855` fires `POST /api/analyze/prompt` alongside the
 * questions and awaits it only when the reader leaves the refine step, so its
 * several seconds are spent while they are answering rather than watching a
 * spinner. This holds that promise, which is what `state.filterAnalysisPromise`
 * was.
 *
 * A promise cannot survive a reload, and the call it stands for spends two LLM
 * calls -- so the result is written into the flow record as soon as it lands
 * rather than being held only in memory. Reloading the refine step then costs
 * nothing, where holding it in memory alone would have bought it twice.
 */
import { analyzePrompt } from '../../api/analyze/analyze.ts'
import type { AnalyzePromptResponse } from '../../api/generated/types.gen.ts'
import { readPlaylistFlow, writePlaylistFlow } from '../flowStore/flowStore.ts'

interface Held {
  readonly prompt: string
  readonly analysis: Promise<AnalyzePromptResponse>
}

let held: Held | undefined

/**
 * Start analysing, and answer nothing. The result is collected later.
 *
 * Its own signal, not the action's: react-router aborts a navigation's
 * request once that navigation is done, and this outlives it by design.
 */
export function startAnalysis(prompt: string, flowId: string): void {
  const analysis = analyzePrompt(prompt, flowId, new AbortController().signal)
  // Attached now, so a failure before `collect` is not an unhandled rejection.
  analysis.catch(() => undefined)
  held = { prompt, analysis }
}

/**
 * Write the analysis into the flow record once it lands.
 *
 * Called after the record exists, never before: the two requests race, and a
 * write from here that beat the questions would be overwritten by them.
 */
export function keepAnalysis(prompt: string): void {
  const started = collectAnalysis(prompt)
  if (!started) return

  void started
    .then((analysis) => {
      const flow = readPlaylistFlow()
      // A newer prompt owns the record by now; this analysis is stale.
      if (flow?.prompt !== prompt) return
      writePlaylistFlow({ ...flow, analysis })
    })
    .catch(() => undefined)
}

/** The analysis started for this prompt, if one was and it is still held. */
export function collectAnalysis(
  prompt: string,
): Promise<AnalyzePromptResponse> | undefined {
  return held?.prompt === prompt ? held.analysis : undefined
}

/** Drop what is held, once its flow has reached a result. */
export function forgetAnalysis(): void {
  held = undefined
}
