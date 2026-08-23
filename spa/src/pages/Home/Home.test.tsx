import { render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { LibrarySyncProvider } from '../../components/organisms/LibrarySyncProvider/LibrarySyncProvider.tsx'
import type { HistoryPage } from '../../libs/loadHistory/loadHistory.ts'
import { Home } from './Home.tsx'

const EMPTY: HistoryPage = { items: [], total: 0, failed: false }

/** A library that has been synced and is sitting idle. */
const IDLE = {
  track_count: 80058,
  synced_at: new Date().toISOString(),
  is_syncing: false,
  plex_connected: true,
}

/** The page on its own route, with the loader stubbed.

    The provider stands in for the shell, which owns the sync poller the
    mode cards read. */
function renderPage(page: HistoryPage = EMPTY, status: object = IDLE) {
  server.use(http.get('/api/library/status', () => HttpResponse.json(status)))
  const router = createMemoryRouter([
    {
      path: '/',
      loader: () => page,
      Component: () => (
        <LibrarySyncProvider>
          <Home />
        </LibrarySyncProvider>
      ),
    },
  ])
  return render(<RouterProvider router={router} />)
}

describe('Home', () => {
  it('opens with the question rather than a wizard', async () => {
    // `frontend/index.html:47` opened here with a setup wizard; Settings is
    // the only configuration surface now.
    renderPage()

    expect(
      await screen.findByRole('heading', {
        name: 'What do you want to listen to?',
      }),
    ).toBeVisible()
  })

  it.each([
    ['Playlist from Prompt', '/playlist/prompt'],
    ['Playlist from Seed', '/playlist/seed'],
    ['Recommend Album', '/recommend'],
  ])('offers %s', async (name, href) => {
    renderPage()

    expect(
      await screen.findByRole('link', { name: new RegExp(name) }),
    ).toHaveAttribute('href', href)
  })

  it('offers the three as links, so each opens in a new tab', async () => {
    // `frontend/index.html:189` drew them as buttons behind a click handler.
    renderPage()

    await screen.findByRole('heading', { name: 'Recent activity' })
    expect(
      screen.queryByRole('button', { name: /Playlist from/ }),
    ).not.toBeInTheDocument()
  })

  it('carries the history under them', async () => {
    renderPage({
      items: [
        {
          id: 'p1',
          title: 'Rainy Sunday',
          prompt: 'wet afternoon',
          track_count: 12,
          created_at: new Date().toISOString(),
          type: 'prompt_playlist',
        },
      ],
      total: 1,
      failed: false,
    })

    expect(
      await screen.findByRole('link', { name: 'Rainy Sunday' }),
    ).toBeVisible()
  })

  describe('while the library is syncing', () => {
    const SYNCING = { ...IDLE, is_syncing: true }

    it.each(['Playlist from Prompt', 'Playlist from Seed', 'Recommend Album'])(
      'shuts %s, since the cache it would read is mid-rewrite',
      async (name) => {
        renderPage(EMPTY, SYNCING)

        // The first poll has not answered on the first paint.
        await waitFor(() => {
          expect(
            screen.getByRole('link', { name: new RegExp(name) }),
          ).toHaveAttribute('aria-disabled', 'true')
        })
      },
    )

    it('says why, rather than dimming three cards without a reason', async () => {
      renderPage(EMPTY, SYNCING)

      expect(await screen.findByText(/Library data is syncing/)).toBeVisible()
    })

    it('opens them again once it is done', async () => {
      renderPage()

      const card = await screen.findByRole('link', { name: /Recommend Album/ })
      expect(card).toHaveAttribute('aria-disabled', 'false')
    })
  })

  it('still renders everything else when the history could not be read', async () => {
    renderPage({ items: [], total: 0, failed: true })

    expect(
      await screen.findByRole('link', { name: /Recommend Album/ }),
    ).toBeVisible()
    expect(screen.getByText('Could not load history.')).toBeVisible()
  })
})
