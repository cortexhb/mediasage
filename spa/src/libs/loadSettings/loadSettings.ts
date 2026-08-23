/**
 * What the Settings route reads before it renders.
 *
 * Every read here is cheap and idempotent, which is what makes it a loader
 * rather than an action. An Ollama server is not asked anything: the form
 * probes the endpoint in the field, which is not always the saved one.
 *
 * The library counts are deliberately absent — they load through a fetcher in
 * `libs/loadStats`, so a save never waits on them.
 */
import type { LoaderFunctionArgs } from 'react-router'

import { readConfig, readSetupStatus } from '../../api/config/config.ts'
import type {
  ConfigResponse,
  SetupStatusResponse,
} from '../../api/generated/types.gen.ts'

export interface SettingsData {
  readonly config: ConfigResponse
  readonly setup: SetupStatusResponse
}

export async function loadSettings({
  request,
}: LoaderFunctionArgs): Promise<SettingsData> {
  const [config, setup] = await Promise.all([
    readConfig(request.signal),
    readSetupStatus(request.signal),
  ])

  return { config, setup }
}
