/**
 * What the Settings route reads before it renders.
 *
 * Every read here is cheap and idempotent, which is what makes it a loader
 * rather than an action. An Ollama server is not asked anything: the form
 * probes the endpoint in the field, which is not always the saved one.
 *
 * The schema is read too, because it is where the form's fields come from —
 * see `libs/patchFields`. It is static, so it costs a cached round-trip.
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
import { readSchema } from '../../api/schema/schema.ts'
import type { PatchField } from '../patchFields/patchFields.ts'
import { PatchFields } from '../patchFields/patchFields.ts'

export interface SettingsData {
  readonly config: ConfigResponse
  readonly setup: SetupStatusResponse
  /** Every editable field in every section, as the API declares them. */
  readonly fields: readonly PatchField[]
}

export async function loadSettings({
  request,
}: LoaderFunctionArgs): Promise<SettingsData> {
  const [config, setup, schema] = await Promise.all([
    readConfig(request.signal),
    readSetupStatus(request.signal),
    readSchema(request.signal),
  ])

  return {
    config,
    setup,
    fields: PatchFields.of(schema.components?.schemas ?? {}),
  }
}
