/**
 * Saving the settings form, called from the page rather than a route action.
 *
 * Not an action, and the reason is the wait. A route action is a navigation,
 * and a navigation is not idle until its loaders *and* every active fetcher
 * have revalidated with it — so a save sat behind a seconds-long library
 * read that had nothing to do with it. A plain call costs one round-trip.
 *
 * `POST /api/config` answers with the settings it kept, so nothing needs
 * re-reading afterwards except the setup status, which carries the library
 * list a Plex change can move.
 *
 * Nothing here throws. A save carries what the user typed, including a
 * credential they will not have kept, so replacing the form with an error
 * page loses work no reload can recover — `frontend/app.js:3320` caught
 * everything for the same reason. The message says which kind of failure it
 * was; the values stay on screen either way.
 */
import { readSetupStatus, saveConfig } from '../../api/config/config.ts'
import type {
  ConfigResponse,
  SetupStatusResponse,
} from '../../api/generated/types.gen.ts'
import { ApiError } from '../../api/request/request.ts'
import type { PatchKind } from '../patchFields/patchFields.ts'
import { settingsUpdate } from '../settingsUpdate/settingsUpdate.ts'

/** Anything that is not the API refusing: no answer came back at all. */
const UNREACHABLE = 'Could not reach the server. Nothing was saved.'

export interface SaveOutcome {
  readonly saved: boolean
  readonly message: string
  /** What the API kept, absent when it kept nothing. */
  readonly config?: ConfigResponse | undefined
  /** Re-read only on success, and only for the library list. */
  readonly setup?: SetupStatusResponse | undefined
}

/** The status again, or nothing — a save is not undone by failing to re-read. */
async function refreshedSetup(
  signal: AbortSignal,
): Promise<SetupStatusResponse | undefined> {
  try {
    return await readSetupStatus(signal)
  } catch {
    return undefined
  }
}

export async function saveSettings(
  form: FormData,
  kinds: ReadonlyMap<string, PatchKind>,
  signal: AbortSignal,
): Promise<SaveOutcome> {
  try {
    const config = await saveConfig(settingsUpdate(form, kinds), signal)
    return {
      saved: true,
      message: 'Settings saved',
      config,
      setup: await refreshedSetup(signal),
    }
  } catch (error) {
    if (error instanceof ApiError) {
      return { saved: false, message: error.message }
    }
    return { saved: false, message: UNREACHABLE }
  }
}
