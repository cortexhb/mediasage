/**
 * Loaded before every test file (see `test.setupFiles` in `vitest.config.ts`).
 *
 * Owns the mock network. Requests are intercepted at the boundary rather than
 * by replacing `fetch` per test, so the code under test runs the same request
 * path it runs in the browser. Tests register their own handlers with
 * `server.use(...)`, importing it from `@test`.
 *
 * Owns the settings fixtures too, for the same reason `libs/patchFields` reads
 * the schema: `ConfigResponse` is shaped like `MediasageConfig`, and eight test
 * files hand-rolling that shape is eight files to edit when a section moves.
 *
 * Cleanup is not wired here: with `globals: true`, React Testing Library
 * registers its own `afterEach` teardown against the global hook.
 */
import '@testing-library/jest-dom/vitest'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll } from 'vitest'

import type {
  ConfigResponse,
  SetupStatusResponse,
} from './src/api/generated'
import type { PatchField } from './src/libs/patchFields/patchFields.ts'

// Node 26 owns `localStorage` (undefined without `--localstorage-file`) and
// `sessionStorage` (one store for the whole worker, so state crosses files).
// Vitest keeps whatever the runtime already defines, so jsdom's storage is
// reattached here, off the JSDOM instance Vitest parks on `globalThis.jsdom`.
declare global {
  let jsdom: { window: Window }
}
for (const key of ['localStorage', 'sessionStorage'] as const) {
  Object.defineProperty(globalThis, key, {
    value: jsdom.window[key],
    configurable: true,
    writable: true,
  })
}

export const server = setupServer()

// An unhandled request means the test is not describing what it exercises.
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

afterEach(() => {
  server.resetHandlers()
})

afterAll(() => {
  server.close()
})

/** The settings a backend with nothing unusual about it reports. */
export const CONFIG: ConfigResponse = {
  version: '1.0.0',
  plex_connected: true,
  plex_linked: true,
  llm_configured: true,
  llm_api_key_set: true,
  max_tracks_to_ai: 500,
  max_albums_to_ai: 100,
  is_priced: false,
  is_local_provider: false,
  from_env: [],
  sections: {
    plex: {
      music_library: 'Music',
      server_name: 'Living Room',
      server_id: 'abc123',
    },
    llm: {
      provider: 'anthropic',
      model_analysis: 'claude',
      model_generation: 'claude',
      context_window: 200000,
    },
    defaults: { track_count: 25 },
  },
}

export const SETUP: SetupStatusResponse = {
  data_dir_writable: true,
  plex_connected: true,
  llm_configured: true,
  library_synced: true,
  music_libraries: ['Music'],
}

/**
 * That config with one section written over, keeping the rest.
 *
 * Shallow per section, which is what a test wants: naming `llm` replaces the
 * provider block outright rather than merging a half-provider into it.
 */
export function configWith(
  sections: Partial<ConfigResponse['sections']>,
  rest: Partial<Omit<ConfigResponse, 'sections'>> = {},
): ConfigResponse {
  return {
    ...CONFIG,
    ...rest,
    sections: { ...CONFIG.sections, ...sections },
  }
}

/** The handful of schema fields the settings tests submit. */
export const FIELDS: readonly PatchField[] = [
  {
    section: 'llm',
    field: 'provider',
    name: 'llm.provider',
    label: 'Provider',
    kind: 'text',
  },
  {
    section: 'llm',
    field: 'api_key',
    name: 'llm.api_key',
    label: 'Api Key',
    kind: 'password',
  },
  {
    section: 'llm',
    field: 'model_analysis',
    name: 'llm.model_analysis',
    label: 'Analysis Model',
    kind: 'text',
  },
  {
    section: 'llm',
    field: 'model_generation',
    name: 'llm.model_generation',
    label: 'Generation Model',
    kind: 'text',
  },
  {
    section: 'llm',
    field: 'context_window',
    name: 'llm.context_window',
    label: 'Context Window',
    kind: 'number',
  },
  {
    section: 'llm',
    field: 'smart_generation',
    name: 'llm.smart_generation',
    label: 'Smart Generation',
    kind: 'boolean',
  },
  {
    section: 'llm',
    field: 'endpoint_url',
    name: 'llm.endpoint_url',
    label: 'Endpoint Url',
    kind: 'text',
  },
  {
    section: 'plex',
    field: 'music_library',
    name: 'plex.music_library',
    label: 'Music Library',
    kind: 'text',
  },
]
