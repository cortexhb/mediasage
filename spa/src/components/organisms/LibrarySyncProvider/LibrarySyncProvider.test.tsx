import { render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { useSharedLibrarySync } from '../../../libs/useLibrarySync/useLibrarySync.ts'
import { LibrarySyncProvider } from './LibrarySyncProvider.tsx'

/** A library that has been synced and is sitting idle. */
const IDLE = {
  track_count: 80058,
  synced_at: '2026-08-01T00:00:00Z',
  is_syncing: false,
  plex_connected: true,
}

/** A consumer that renders what it was handed, so a test can read it. */
function Reader({ name }: { readonly name: string }) {
  const sync = useSharedLibrarySync()

  return <p>{`${name}: ${String(sync.status?.track_count ?? 'waiting')}`}</p>
}

describe('LibrarySyncProvider', () => {
  it('hands its state to everything under it', async () => {
    server.use(http.get('/api/library/status', () => HttpResponse.json(IDLE)))

    render(
      <LibrarySyncProvider>
        <Reader name="footer" />
      </LibrarySyncProvider>,
    )

    expect(await screen.findByText('footer: 80058')).toBeVisible()
  })

  it('polls once however many consumers read it', async () => {
    // Three components ask about a sync; three pollers would disagree.
    let polls = 0
    server.use(
      http.get('/api/library/status', () => {
        polls += 1
        return HttpResponse.json(IDLE)
      }),
    )

    render(
      <LibrarySyncProvider>
        <Reader name="footer" />
        <Reader name="settings" />
        <Reader name="home" />
      </LibrarySyncProvider>,
    )

    await waitFor(() => {
      expect(screen.getByText('home: 80058')).toBeVisible()
    })
    expect(polls).toBe(1)
  })

  it('fails loudly where a consumer has no provider above it', () => {
    // Answering with a second poller instead would be silent and wrong.
    expect(() => render(<Reader name="orphan" />)).toThrow(
      'useSharedLibrarySync needs a LibrarySyncProvider',
    )
  })
})
