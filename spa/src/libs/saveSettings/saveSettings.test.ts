import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { saveSettings } from './saveSettings.ts'

/** Enough of what `POST /api/config` answers with to be adopted. */
const CONFIG = {
  version: '1.0.0',
  plex_url: 'http://plex:32400',
  plex_connected: true,
  plex_token_set: true,
  music_library: 'Music',
  llm_provider: 'anthropic',
  llm_configured: true,
  llm_api_key_set: true,
  model_analysis: 'claude',
  model_generation: 'claude',
  max_tracks_to_ai: 500,
  max_albums_to_ai: 100,
  defaults: { track_count: 25 },
  context_window: 200000,
}

const SETUP = {
  data_dir_writable: true,
  plex_connected: true,
  llm_configured: true,
  library_synced: true,
  music_libraries: ['Music', 'Vinyl'],
}

/** The submitted form. */
function form(fields: Record<string, string>): FormData {
  const submitted = new FormData()
  for (const [name, value] of Object.entries(fields)) {
    submitted.append(name, value)
  }
  return submitted
}

/** A save, with a fresh signal nobody aborts. */
function save(fields: Record<string, string>) {
  return saveSettings(form(fields), new AbortController().signal)
}

/** Answer the save and the status re-read that follows it. */
function kept() {
  server.use(
    http.post('/api/config', () => HttpResponse.json(CONFIG)),
    http.get('/api/setup/status', () => HttpResponse.json(SETUP)),
  )
}

describe('saveSettings', () => {
  it('reports a save that was kept', async () => {
    kept()

    const outcome = await save({ plex_url: 'http://plex:32400' })

    expect(outcome.saved).toBe(true)
    expect(outcome.message).toBe('Settings saved')
  })

  it('sends the form as a partial update', async () => {
    let sent: unknown
    kept()
    server.use(
      http.post('/api/config', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json(CONFIG)
      }),
    )

    await save({
      plex_url: 'http://plex:32400',
      plex_token: '',
      music_library: 'Vinyl',
    })

    expect(sent).toEqual({
      plex_url: 'http://plex:32400',
      music_library: 'Vinyl',
    })
  })

  describe('what a kept save hands back', () => {
    it('carries the settings, so nothing has to re-read them', async () => {
      kept()

      expect((await save({ music_library: 'Vinyl' })).config).toEqual(CONFIG)
    })

    it('re-reads the status, which holds the library list', async () => {
      // A Plex change moves it, and `POST /api/config` does not carry it.
      kept()

      expect((await save({ plex_url: 'http://new:32400' })).setup).toEqual(
        SETUP,
      )
    })

    it('stays a save when that re-read fails', async () => {
      server.use(
        http.post('/api/config', () => HttpResponse.json(CONFIG)),
        http.get('/api/setup/status', () => HttpResponse.error()),
      )

      const outcome = await save({ music_library: 'Vinyl' })

      expect(outcome.saved).toBe(true)
      expect(outcome.setup).toBeUndefined()
    })
  })

  describe('when a probe refuses the change', () => {
    it('reports the refusal instead of throwing it', async () => {
      // About the values in the form, so the form shows it.
      server.use(
        http.post('/api/config', () =>
          HttpResponse.json({ detail: 'Model not found' }, { status: 422 }),
        ),
      )

      const outcome = await save({ model_analysis: 'nope' })

      expect(outcome).toEqual({ saved: false, message: 'Model not found' })
    })

    it('reports a rejected empty submission', async () => {
      server.use(
        http.post('/api/config', () =>
          HttpResponse.json(
            { detail: 'No configuration values provided' },
            { status: 400 },
          ),
        ),
      )

      const outcome = await save({ plex_url: '' })

      expect(outcome.saved).toBe(false)
      expect(outcome.message).toBe('No configuration values provided')
    })
  })

  it('keeps the form when the server cannot be reached', async () => {
    // An error page would take a typed credential with it.
    server.use(http.post('/api/config', () => HttpResponse.error()))

    const outcome = await save({ plex_url: 'http://plex' })

    expect(outcome.saved).toBe(false)
    expect(outcome.message).toMatch(/Could not reach the server/)
  })
})
