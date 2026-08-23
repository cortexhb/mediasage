import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { useLibrarySync } from './useLibrarySync.ts'

/** A library that has been synced and is sitting idle. */
const IDLE = {
  track_count: 80058,
  synced_at: '2026-08-01T00:00:00Z',
  is_syncing: false,
  plex_connected: true,
}

/** Nothing synced, and a server there to sync from. */
const UNSYNCED = {
  track_count: 0,
  synced_at: null,
  is_syncing: false,
  plex_connected: true,
}

/** Answer the status poll with `status`, once and thereafter. */
function reporting(status: object) {
  server.use(http.get('/api/library/status', () => HttpResponse.json(status)))
}

/** Answer every sync request, counting them. */
function accepting(): { started: number } {
  const calls = { started: 0 }
  server.use(
    http.post('/api/library/sync', () => {
      calls.started += 1
      return HttpResponse.json({ started: true, blocking: false })
    }),
  )
  return calls
}

describe('useLibrarySync', () => {
  it('reports nothing until the first poll answers', () => {
    reporting(IDLE)

    const { result } = renderHook(() => useLibrarySync())

    expect(result.current.status).toBeUndefined()
  })

  it('reports what the poll answered', async () => {
    reporting(IDLE)

    const { result } = renderHook(() => useLibrarySync())

    await waitFor(() => {
      expect(result.current.status?.track_count).toBe(80058)
    })
  })

  it('never starts a sync on its own', async () => {
    // `frontend/app.js:2352` did, on an empty library, spending hours of
    // somebody's Plex server for opening a page.
    const calls = accepting()
    reporting(UNSYNCED)

    const { result } = renderHook(() => useLibrarySync())
    await waitFor(() => {
      expect(result.current.unsynced).toBe(true)
    })

    expect(calls.started).toBe(0)
  })

  describe('what it calls an empty library', () => {
    it('is unsynced with no tracks, no previous sync, and a server', async () => {
      reporting(UNSYNCED)

      const { result } = renderHook(() => useLibrarySync())

      await waitFor(() => {
        expect(result.current.unsynced).toBe(true)
      })
      expect(result.current.blocking).toBe(false)
    })

    it('is not unsynced with no Plex to sync from', async () => {
      reporting({ ...UNSYNCED, plex_connected: false })

      const { result } = renderHook(() => useLibrarySync())

      await waitFor(() => {
        expect(result.current.status).toBeDefined()
      })
      expect(result.current.unsynced).toBe(false)
    })

    it('is blocking while the first sync runs', async () => {
      reporting({ ...UNSYNCED, is_syncing: true })

      const { result } = renderHook(() => useLibrarySync())

      await waitFor(() => {
        expect(result.current.blocking).toBe(true)
      })
      expect(result.current.unsynced).toBe(false)
    })

    it('is not blocking when a resync runs over tracks already held', async () => {
      // The app is usable meanwhile; blocking it would be a regression.
      reporting({ ...IDLE, is_syncing: true })

      const { result } = renderHook(() => useLibrarySync())

      await waitFor(() => {
        expect(result.current.status?.is_syncing).toBe(true)
      })
      expect(result.current.blocking).toBe(false)
    })

    it('is neither once a sync has run, whatever it found', async () => {
      reporting({ ...UNSYNCED, synced_at: '2026-08-01T00:00:00Z' })

      const { result } = renderHook(() => useLibrarySync())

      await waitFor(() => {
        expect(result.current.status).toBeDefined()
      })
      expect(result.current.unsynced).toBe(false)
      expect(result.current.blocking).toBe(false)
    })
  })

  describe('polling', () => {
    it('asks once and stops while nothing is syncing', async () => {
      let polls = 0
      server.use(
        http.get('/api/library/status', () => {
          polls += 1
          return HttpResponse.json(IDLE)
        }),
      )

      const { result } = renderHook(() => useLibrarySync())
      await waitFor(() => {
        expect(result.current.status).toBeDefined()
      })

      // A request a second is only worth it while a sync runs.
      await new Promise((resume) => setTimeout(resume, 1200))
      expect(polls).toBe(1)
    })

    it('keeps asking while a sync runs', async () => {
      let polls = 0
      server.use(
        http.get('/api/library/status', () => {
          polls += 1
          return HttpResponse.json({ ...IDLE, is_syncing: true })
        }),
      )

      renderHook(() => useLibrarySync())

      await waitFor(
        () => {
          expect(polls).toBeGreaterThan(1)
        },
        { timeout: 3000 },
      )
    })

    it('stops when the caller goes away', async () => {
      let polls = 0
      server.use(
        http.get('/api/library/status', () => {
          polls += 1
          return HttpResponse.json({ ...IDLE, is_syncing: true })
        }),
      )
      const { result, unmount } = renderHook(() => useLibrarySync())
      await waitFor(() => {
        expect(result.current.status).toBeDefined()
      })

      unmount()
      const asked = polls
      await new Promise((resume) => setTimeout(resume, 1200))

      expect(polls).toBe(asked)
    })
  })

  describe('starting one', () => {
    it('asks the server when told to', async () => {
      const calls = accepting()
      reporting(IDLE)
      const { result } = renderHook(() => useLibrarySync())
      await waitFor(() => {
        expect(result.current.status).toBeDefined()
      })

      act(() => {
        result.current.start()
      })

      await waitFor(() => {
        expect(calls.started).toBe(1)
      })
    })

    it('polls again once the sync is asked for', async () => {
      let polls = 0
      accepting()
      server.use(
        http.get('/api/library/status', () => {
          polls += 1
          return HttpResponse.json(IDLE)
        }),
      )
      const { result } = renderHook(() => useLibrarySync())
      await waitFor(() => {
        expect(polls).toBe(1)
      })

      act(() => {
        result.current.start()
      })

      await waitFor(() => {
        expect(polls).toBe(2)
      })
    })

    it('treats "already running" as the outcome asked for', async () => {
      reporting(IDLE)
      server.use(
        http.post('/api/library/sync', () =>
          HttpResponse.json(
            { detail: 'Sync already in progress' },
            { status: 409 },
          ),
        ),
      )
      const { result } = renderHook(() => useLibrarySync())
      await waitFor(() => {
        expect(result.current.status).toBeDefined()
      })

      act(() => {
        result.current.start()
      })

      await waitFor(() => {
        expect(result.current.error).toBe('')
      })
    })

    it('reports a refusal it cannot explain away', async () => {
      reporting(IDLE)
      server.use(
        http.post('/api/library/sync', () =>
          HttpResponse.json(
            { detail: 'Plex is not connected' },
            { status: 503 },
          ),
        ),
      )
      const { result } = renderHook(() => useLibrarySync())
      await waitFor(() => {
        expect(result.current.status).toBeDefined()
      })

      act(() => {
        result.current.start()
      })

      await waitFor(() => {
        expect(result.current.error).toBe('Plex is not connected')
      })
    })
  })

  describe('errors', () => {
    it('reports a status read that failed', async () => {
      server.use(
        http.get('/api/library/status', () =>
          HttpResponse.json({ detail: 'database is locked' }, { status: 500 }),
        ),
      )

      const { result } = renderHook(() => useLibrarySync())

      await waitFor(() => {
        expect(result.current.error).toBe('database is locked')
      })
    })

    it('surfaces what a failed sync left behind', async () => {
      reporting({ ...IDLE, error: 'Plex went away mid-sync' })

      const { result } = renderHook(() => useLibrarySync())

      await waitFor(() => {
        expect(result.current.error).toBe('Plex went away mid-sync')
      })
    })
  })
})
