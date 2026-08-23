import { render, screen } from '@testing-library/react'
import { userEvent } from 'vitest/browser'
import { describe, expect, it, vi } from 'vitest'

import type { LibraryCacheStatusResponse } from '../../../api/generated/types.gen.ts'
import type { LibrarySync } from '../../../libs/useLibrarySync/useLibrarySync.ts'
import { LibrarySyncContext } from '../../../libs/useLibrarySync/useLibrarySync.ts'
import { Footer } from './Footer.tsx'

/**
 * Real Chromium, not jsdom, because this asserts on the `<dialog>`.
 *
 * jsdom 30.0.1 implements none of `show`, `showModal` or `close` -- see
 * `vitest.config.ts`. Everything the bar does without opening the dialog is
 * tested in `Footer.test.tsx`.
 *
 * The context is filled by hand rather than by `LibrarySyncProvider`: the
 * browser project has no mock network, and what is under test here is what
 * the bar does with a state, not how it reads one.
 */

/** A library mid-resync, with tracks already cached behind it. */
const RESYNC: LibraryCacheStatusResponse = {
  track_count: 80058,
  synced_at: '2026-08-01T00:00:00Z',
  is_syncing: true,
  plex_connected: true,
  sync_progress: { phase: 'fetching_genres', current: 3, total: 9 },
}

/** The bar over a sync state, with no poller behind it. */
function showing(status: LibraryCacheStatusResponse, blocking = false) {
  const sync: LibrarySync = {
    status,
    blocking,
    unsynced: false,
    error: '',
    start: vi.fn(),
  }

  return render(
    <LibrarySyncContext value={sync}>
      <Footer />
    </LibrarySyncContext>,
  )
}

/** The bar's progress text, which is the way back into the dialog. */
function progress(): HTMLElement {
  return screen.getByRole('button', { name: /Syncing/ })
}

describe('Footer', () => {
  it('opens the dialog on its own for a first sync', () => {
    // Nothing to play from until it finishes.
    showing({ ...RESYNC, track_count: 0, synced_at: null }, true)

    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('leaves a resync to the bar, since the library is already usable', () => {
    showing(RESYNC)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens from the progress text', async () => {
    // `frontend/app.js:2244` hid it with no way back, leaving only the bar.
    showing(RESYNC)

    await userEvent.click(progress())

    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('names the phase inside, which the bar has no room for', async () => {
    showing(RESYNC)

    await userEvent.click(progress())

    expect(screen.getByText(/Enriching albums with genres/)).toBeVisible()
  })

  it('closes on the button and reopens from the bar', async () => {
    showing(RESYNC)
    await userEvent.click(progress())

    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await userEvent.click(progress())
    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('closes on Escape and reopens from the bar', async () => {
    showing(RESYNC)
    await userEvent.click(progress())

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await userEvent.click(progress())
    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('keeps the sync running when the dialog is dismissed', async () => {
    // Dismissing a view of the sync must never be dismissing the sync.
    showing(RESYNC)
    await userEvent.click(progress())

    await userEvent.keyboard('{Escape}')

    expect(progress()).toBeVisible()
  })

  it('says a first sync runs once', () => {
    showing({ ...RESYNC, track_count: 0, synced_at: null }, true)

    expect(screen.getByText(/This runs once/)).toBeVisible()
  })

  it('says a resync leaves the app usable', async () => {
    showing(RESYNC)

    await userEvent.click(progress())

    expect(screen.getByText(/stays usable/)).toBeVisible()
  })
})
