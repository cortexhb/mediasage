import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { LibraryStatsResponse } from '../../../api/generated/types.gen.ts'
import { LibraryStats } from './LibraryStats.tsx'

/** What a synced library of some size reports. */
const STATS = {
  total_tracks: 52341,
  genres: [{ name: 'Rock', count: 900 }],
  decades: [{ name: '1970s', count: 400 }],
}

/**
 * The component beside the resource route it fetches.
 *
 * `answer` stands in for `loadStats`; a promise it never settles is what a
 * read still in flight looks like.
 */
function renderStats(
  answer: (
    connected: string | null,
  ) => LibraryStatsResponse | null | Promise<LibraryStatsResponse | null>,
) {
  const router = createMemoryRouter([
    { index: true, Component: () => <LibraryStats connected /> },
    {
      path: 'settings/stats',
      loader: ({ request }) =>
        answer(new URL(request.url).searchParams.get('connected')),
    },
  ])
  return render(<RouterProvider router={router} />)
}

describe('LibraryStats', () => {
  it('says it is working while the counts are still being read', async () => {
    renderStats(() => new Promise<null>(() => undefined))

    expect(await screen.findByText(/hold tight/)).toBeVisible()
  })

  it('says so when neither source could answer', async () => {
    renderStats(() => null)

    expect(
      await screen.findByText('Library statistics are unavailable.'),
    ).toBeVisible()
  })

  it('shows the counts once they land', async () => {
    renderStats(() => STATS)

    expect(await screen.findByText('52,341')).toBeVisible()
  })

  it('tells the route whether Plex answers, so it can skip a live read', async () => {
    let asked: string | null = null
    renderStats((connected) => {
      asked = connected
      return STATS
    })

    await screen.findByText('52,341')
    expect(asked).toBe('true')
  })
})
