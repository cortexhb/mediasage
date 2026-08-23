/**
 * What is wrong with a custom provider's endpoint and context window.
 *
 * Pure, and checked as the field is edited rather than on submit, because
 * `POST /api/config` answers a single 422 for the whole form — which field
 * was at fault is only knowable here. Mirrors `frontend/app.js:1946`.
 */
import { contextWindowError } from '../contextWindowError/contextWindowError.ts'

export interface CustomErrors {
  readonly url: string | undefined
  readonly contextWindow: string | undefined
}

/** An address that is not http(s), or is not an address at all. */
function urlError(value: string): string | undefined {
  if (value.trim() === '') return undefined
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    return 'Invalid URL format'
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return 'Must use http or https protocol'
  }
  return undefined
}

export function customErrors(url: string, contextWindow: string): CustomErrors {
  return {
    url: urlError(url),
    contextWindow: contextWindowError(contextWindow),
  }
}
