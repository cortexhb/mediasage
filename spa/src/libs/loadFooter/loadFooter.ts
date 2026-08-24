/**
 * The version and model the status bar names, on a route of its own.
 *
 * A fetcher rather than a loader on the shell: this is one read that every
 * navigation would otherwise wait on, and the bar it fills is informational.
 * `libs/loadStats` says more about why loader data is the wrong place.
 *
 * Read by `components/organisms/Footer`.
 */
import type { LoaderFunctionArgs } from 'react-router'

import { readConfig } from '../../api/config/config.ts'
import type { ConfigResponse } from '../../api/generated/types.gen.ts'

export interface FooterFacts {
  readonly version: string
  readonly model: string
  /** A local model has no price, so a run reports tokens and no cost. */
  readonly local: boolean
}

/**
 * Which model name the bar shows, as `frontend/app.js:2050` chose it.
 *
 * Both names only when they differ, since one model configured for both roles
 * would otherwise be printed twice.
 */
function modelOf(config: ConfigResponse): string {
  if (!config.llm_configured) return 'llm not configured'

  const { model_analysis: analysis, model_generation: generation } =
    config.sections.llm
  if (analysis && generation && analysis !== generation) {
    return `${analysis} / ${generation}`
  }
  // An unset model name is the empty string, and must fall through.
  const named = [generation, analysis].find(
    (name) => name !== undefined && name !== '',
  )
  return named ?? config.sections.llm.provider
}

/**
 * `GET /footer` — what the status bar names on its left.
 *
 * A failure answers nothing rather than faulting: the bar is under every
 * page, and no page is broken by not knowing which model is configured.
 */
export async function loadFooter({
  request,
}: Pick<LoaderFunctionArgs, 'request'>): Promise<FooterFacts | null> {
  try {
    const config = await readConfig(request.signal)
    return {
      version: config.version,
      model: modelOf(config),
      local: config.is_local_provider ?? false,
    }
  } catch {
    return null
  }
}
