import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import type { ResultListItem } from '../../../api/generated/types.gen.ts'
import type { HistoryPage } from '../../../libs/loadHistory/loadHistory.ts'
import { HistoryFeed } from './HistoryFeed.tsx'

/** A saved result, with only what a test cares about overridden. */
function saved(over: Partial<ResultListItem> = {}): ResultListItem {
  return {
    id: 'a',
    title: 'One',
    prompt: 'a prompt',
    track_count: 10,
    created_at: new Date().toISOString(),
    type: 'prompt_playlist',
    ...over,
  }
}

const PLAYLIST = saved({ id: 'p1', title: 'Rainy Sunday' })
const ALBUM = saved({
  id: 'a1',
  title: 'Pink Moon',
  type: 'album_recommendation',
})

function page(over: Partial<HistoryPage> = {}): HistoryPage {
  return { items: [PLAYLIST, ALBUM], total: 2, failed: false, ...over }
}

/** The feed inside a router, since its entries are links. */
function renderFeed(data: HistoryPage = page()) {
  const router = createMemoryRouter([
    { index: true, Component: () => <HistoryFeed page={data} /> },
  ])
  return render(<RouterProvider router={router} />)
}

describe('HistoryFeed', () => {
  it('lists what the loader already read', () => {
    renderFeed()

    expect(screen.getByRole('link', { name: 'Rainy Sunday' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Pink Moon' })).toBeVisible()
  })

  it('invites a first result rather than showing an empty list', () => {
    renderFeed(page({ items: [], total: 0 }))

    expect(
      screen.getByText('Your playlist and album history will appear here'),
    ).toBeVisible()
  })

  it('says a failed read failed, which is not the same as empty', () => {
    renderFeed(page({ items: [], total: 0, failed: true }))

    expect(screen.getByText('Could not load history.')).toBeVisible()
  })

  it('heads each day once, however many entries it holds', () => {
    renderFeed()

    expect(screen.getAllByRole('heading', { name: 'Today' })).toHaveLength(1)
  })

  describe('filtering', () => {
    it('counts each kind on its chip', () => {
      renderFeed()

      expect(screen.getByRole('button', { name: /^All/ })).toHaveTextContent(
        'All 2',
      )
      expect(
        screen.getByRole('button', { name: /^Playlists/ }),
      ).toHaveTextContent('Playlists 1')
    })

    it('shows only what the chosen chip admits', async () => {
      renderFeed()

      await userEvent.click(screen.getByRole('button', { name: /^Albums/ }))

      expect(screen.getByRole('link', { name: 'Pink Moon' })).toBeVisible()
      expect(
        screen.queryByRole('link', { name: 'Rainy Sunday' }),
      ).not.toBeInTheDocument()
    })

    it('keeps the counts describing the whole page, not the filter', async () => {
      renderFeed()

      await userEvent.click(screen.getByRole('button', { name: /^Albums/ }))

      expect(screen.getByRole('button', { name: /^All/ })).toHaveTextContent(
        'All 2',
      )
    })
  })

  describe('deleting', () => {
    it('asks before it deletes', async () => {
      let asked = false
      server.use(
        http.delete('/api/results/:id', () => {
          asked = true
          return new HttpResponse(null, { status: 204 })
        }),
      )
      renderFeed()

      await userEvent.click(
        screen.getByRole('button', { name: 'Delete Rainy Sunday' }),
      )

      expect(asked).toBe(false)
      expect(
        screen.getByRole('button', { name: 'Confirm deleting Rainy Sunday' }),
      ).toBeInTheDocument()
    })

    it('removes it on the second click', async () => {
      server.use(
        http.delete(
          '/api/results/:id',
          () => new HttpResponse(null, { status: 204 }),
        ),
      )
      renderFeed()

      await userEvent.click(
        screen.getByRole('button', { name: 'Delete Rainy Sunday' }),
      )
      await userEvent.click(
        screen.getByRole('button', { name: 'Confirm deleting Rainy Sunday' }),
      )

      await waitFor(() => {
        expect(
          screen.queryByRole('link', { name: 'Rainy Sunday' }),
        ).not.toBeInTheDocument()
      })
    })

    it('arms one entry at a time', async () => {
      renderFeed()

      await userEvent.click(
        screen.getByRole('button', { name: 'Delete Rainy Sunday' }),
      )
      await userEvent.click(
        screen.getByRole('button', { name: 'Delete Pink Moon' }),
      )

      expect(
        screen.getByRole('button', { name: 'Delete Rainy Sunday' }),
      ).toBeInTheDocument()
    })

    it('puts the row back when the server refuses', async () => {
      server.use(
        http.delete('/api/results/:id', () =>
          HttpResponse.json({ detail: 'nope' }, { status: 500 }),
        ),
      )
      renderFeed()

      await userEvent.click(
        screen.getByRole('button', { name: 'Delete Rainy Sunday' }),
      )
      await userEvent.click(
        screen.getByRole('button', { name: 'Confirm deleting Rainy Sunday' }),
      )

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'That could not be deleted.',
      )
      expect(screen.getByRole('link', { name: 'Rainy Sunday' })).toBeVisible()
    })
  })

  describe('loading more', () => {
    it('offers it only while entries remain unread', () => {
      renderFeed()

      expect(
        screen.queryByRole('button', { name: 'Load more' }),
      ).not.toBeInTheDocument()
    })

    it('appends the next page rather than replacing this one', async () => {
      server.use(
        http.get('/api/results', () =>
          HttpResponse.json({
            results: [saved({ id: 'p2', title: 'Late Night' })],
            total: 3,
          }),
        ),
      )
      renderFeed(page({ total: 3 }))

      await userEvent.click(screen.getByRole('button', { name: 'Load more' }))

      expect(
        await screen.findByRole('link', { name: 'Late Night' }),
      ).toBeVisible()
      expect(screen.getByRole('link', { name: 'Rainy Sunday' })).toBeVisible()
    })

    it('asks for what comes after what it holds', async () => {
      let asked = ''
      server.use(
        http.get('/api/results', ({ request }) => {
          asked = new URL(request.url).search
          return HttpResponse.json({ results: [], total: 3 })
        }),
      )
      renderFeed(page({ total: 3 }))

      await userEvent.click(screen.getByRole('button', { name: 'Load more' }))

      await waitFor(() => {
        expect(asked).toBe('?limit=20&offset=2')
      })
    })

    it('reports a failure without losing what is on screen', async () => {
      server.use(
        http.get('/api/results', () =>
          HttpResponse.json({ detail: 'nope' }, { status: 500 }),
        ),
      )
      renderFeed(page({ total: 3 }))

      await userEvent.click(screen.getByRole('button', { name: 'Load more' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Could not load more history.',
      )
      expect(screen.getByRole('link', { name: 'Rainy Sunday' })).toBeVisible()
    })
  })
})
