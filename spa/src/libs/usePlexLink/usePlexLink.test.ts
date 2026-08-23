import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { usePlexLink } from './usePlexLink.ts'

const PIN = {
  pin_id: 42,
  code: 'WXYZ',
  url: 'https://app.plex.tv/auth/#!?code=WXYZ',
  expires_in: 900,
}

const SERVERS = [{ id: 'abc123', name: 'Living Room', owned: true }]

/** Script the pin exchange, answering every poll the same way. */
function exchange(poll: object) {
  server.use(
    http.post('/api/plex/link', () => HttpResponse.json(PIN)),
    http.get('/api/plex/link/:pin', () => HttpResponse.json(poll)),
  )
}

describe('usePlexLink', () => {
  it('starts idle, so a card renders what the config says', () => {
    const { result } = renderHook(() => usePlexLink(false))

    expect(result.current.stage).toBe('idle')
    expect(result.current.signedIn).toBe(false)
  })

  it('waits on the code only once there is one to show', async () => {
    exchange({ state: 'pending' })
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.signIn(null)
    })

    expect(result.current.stage).toBe('busy')
    await waitFor(() => {
      expect(result.current.stage).toBe('waiting')
    })
    expect(result.current.code).toBe('WXYZ')
  })

  it('sends the opened tab to plex.tv once the address is known', async () => {
    exchange({ state: 'pending' })
    const target = { location: { href: '' }, close: () => undefined }
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.signIn(target as unknown as Window)
    })

    await waitFor(() => {
      expect(target.location.href).toBe(PIN.url)
    })
  })

  it('polls until the pin is approved, then offers the servers', async () => {
    exchange({ state: 'linked', servers: SERVERS })
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.signIn(null)
    })

    await waitFor(() => {
      expect(result.current.stage).toBe('choosing')
    })
    expect(result.current.servers).toEqual(SERVERS)
  })

  it('remembers the sign-in, since the loaded config predates it', async () => {
    exchange({ state: 'linked', servers: SERVERS })
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.signIn(null)
    })

    await waitFor(() => {
      expect(result.current.signedIn).toBe(true)
    })
  })

  it('stops polling when the pin is abandoned', async () => {
    let polls = 0
    server.use(
      http.post('/api/plex/link', () => HttpResponse.json(PIN)),
      http.get('/api/plex/link/:pin', () => {
        polls += 1
        return HttpResponse.json({ state: 'pending' })
      }),
    )
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.signIn(null)
    })
    await waitFor(() => {
      expect(polls).toBe(1)
    })
    act(() => {
      result.current.cancel()
    })

    expect(result.current.stage).toBe('idle')
  })

  it('reports a pin plex.tv would not create', async () => {
    server.use(
      http.post('/api/plex/link', () =>
        HttpResponse.json(
          { detail: 'Could not reach plex.tv' },
          { status: 502 },
        ),
      ),
    )
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.signIn(null)
    })

    await waitFor(() => {
      expect(result.current.error).toBe('Could not reach plex.tv')
    })
    expect(result.current.stage).toBe('idle')
  })

  it('ends the poll rather than repeating it once the pin has expired', async () => {
    server.use(
      http.post('/api/plex/link', () => HttpResponse.json(PIN)),
      http.get('/api/plex/link/:pin', () =>
        HttpResponse.json(
          { detail: 'Plex refused the request: 404' },
          { status: 502 },
        ),
      ),
    )
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.signIn(null)
    })

    await waitFor(() => {
      expect(result.current.stage).toBe('idle')
    })
    expect(result.current.error).toContain('404')
  })

  it('hands back what choosing a server left in force', async () => {
    const chosen = {
      linked: true,
      connected: true,
      server_name: 'Living Room',
      music_libraries: ['Music'],
    }
    server.use(http.post('/api/plex/server', () => HttpResponse.json(chosen)))
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.choose('abc123')
    })

    await waitFor(() => {
      expect(result.current.linked).toEqual(chosen)
    })
  })

  it('returns to the picker when the chosen server will not answer', async () => {
    server.use(
      http.post('/api/plex/server', () =>
        HttpResponse.json(
          { detail: 'Plex listed no address' },
          { status: 422 },
        ),
      ),
    )
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.choose('abc123')
    })

    await waitFor(() => {
      expect(result.current.stage).toBe('choosing')
    })
    expect(result.current.error).toBe('Plex listed no address')
  })

  it('forgets the sign-in when signing out', async () => {
    server.use(
      http.delete('/api/plex/link', () =>
        HttpResponse.json({ linked: false, connected: false }),
      ),
    )
    const { result } = renderHook(() => usePlexLink(false))

    act(() => {
      result.current.signOut()
    })

    await waitFor(() => {
      expect(result.current.linked).toBeDefined()
    })
    expect(result.current.linked?.linked).toBe(false)
    expect(result.current.signedIn).toBe(false)
  })

  describe('when the configuration already holds a sign-in', () => {
    it('lists the servers on mount, so the choice is offered upfront', async () => {
      server.use(
        http.get('/api/plex/servers', () =>
          HttpResponse.json({ state: 'linked', servers: SERVERS }),
        ),
      )
      const { result } = renderHook(() => usePlexLink(true))

      await waitFor(() => {
        expect(result.current.servers).toEqual(SERVERS)
      })
      expect(result.current.stage).toBe('idle')
    })

    it('says nothing when plex.tv will not list them', async () => {
      // The card still names the connected server; this is not news.
      server.use(http.get('/api/plex/servers', () => HttpResponse.error()))
      const { result } = renderHook(() => usePlexLink(true))

      await waitFor(() => {
        expect(result.current.stage).toBe('idle')
      })
      expect(result.current.error).toBe('')
    })

    it('asks for nothing when there is no sign-in to list against', () => {
      // No handler is registered: an unhandled request fails the test.
      const { result } = renderHook(() => usePlexLink(false))

      expect(result.current.servers).toEqual([])
    })
  })
})
