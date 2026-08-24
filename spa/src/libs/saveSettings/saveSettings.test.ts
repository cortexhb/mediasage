import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { CONFIG, FIELDS, SETUP, server } from '@test'
import { PatchFields } from '../patchFields/patchFields.ts'
import { saveSettings } from './saveSettings.ts'

const KINDS = PatchFields.kinds(FIELDS)

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
  return saveSettings(form(fields), KINDS, new AbortController().signal)
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

    const outcome = await save({ 'plex.music_library': 'Music' })

    expect(outcome.saved).toBe(true)
    expect(outcome.message).toBe('Settings saved')
  })

  it('sends the form as a partial update, grouped by section', async () => {
    let sent: unknown
    kept()
    server.use(
      http.post('/api/config', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json(CONFIG)
      }),
    )

    await save({
      'llm.api_key': '',
      'plex.music_library': 'Vinyl',
      'llm.model_analysis': 'claude',
    })

    expect(sent).toEqual({
      plex: { music_library: 'Vinyl' },
      llm: { model_analysis: 'claude' },
    })
  })

  describe('what a kept save hands back', () => {
    it('carries the settings, so nothing has to re-read them', async () => {
      kept()

      expect((await save({ 'plex.music_library': 'Vinyl' })).config).toEqual(
        CONFIG,
      )
    })

    it('re-reads the status, which holds the library list', async () => {
      // A sign-in moves it, and `POST /api/config` does not carry it.
      kept()

      expect((await save({ 'plex.music_library': 'Vinyl' })).setup).toEqual(
        SETUP,
      )
    })

    it('stays a save when that re-read fails', async () => {
      server.use(
        http.post('/api/config', () => HttpResponse.json(CONFIG)),
        http.get('/api/setup/status', () => HttpResponse.error()),
      )

      const outcome = await save({ 'plex.music_library': 'Vinyl' })

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

      const outcome = await save({ 'llm.model_analysis': 'nope' })

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

      const outcome = await save({ 'plex.music_library': '' })

      expect(outcome.saved).toBe(false)
      expect(outcome.message).toBe('No configuration values provided')
    })
  })

  it('keeps the form when the server cannot be reached', async () => {
    // An error page would take a typed credential with it.
    server.use(http.post('/api/config', () => HttpResponse.error()))

    const outcome = await save({ 'plex.music_library': 'Music' })

    expect(outcome.saved).toBe(false)
    expect(outcome.message).toMatch(/Could not reach the server/)
  })
})
