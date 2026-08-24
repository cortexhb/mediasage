import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Mock } from 'vitest'
import { describe, expect, it, vi } from 'vitest'

import { server } from '@test'
import type { AlbumFiltersData } from '../../libs/loadAlbumFilters/loadAlbumFilters.ts'
import { ALBUM_PREVIEW } from '../../libs/previewAlbums/previewAlbums.ts'
import { previewAlbums } from '../../libs/previewAlbums/previewAlbums.ts'
import { AlbumFilters } from './AlbumFilters.tsx'

/** The route's action, stubbed, so a submit is read rather than followed. */
type ActionSpy = Mock<(args: { request: Request }) => null>

const DATA: AlbumFiltersData = {
  availableGenres: [
    { name: 'Jazz', count: 400 },
    { name: 'Rock', count: 900 },
  ],
  availableDecades: [{ name: '1970s', count: 30 }],
  selectedGenres: ['Jazz'],
  selectedDecades: [],
  fromPrompt: true,
  ceiling: 35_000,
  mode: 'library',
  familiarity: 'any',
}

/** The page on its own route, with the preview route beside it. */
function showPage(
  data: AlbumFiltersData = DATA,
  action: ActionSpy = vi.fn(() => null),
): ActionSpy {
  server.use(
    http.get('/api/recommend/albums/preview', () =>
      HttpResponse.json({ matching_albums: 900, albums_to_send: 500 }),
    ),
  )
  const router = createMemoryRouter(
    [
      {
        path: '/recommend/filters',
        loader: () => data,
        action,
        Component: AlbumFilters,
      },
      { path: ALBUM_PREVIEW, loader: previewAlbums },
    ],
    { initialEntries: ['/recommend/filters'] },
  )
  render(<RouterProvider router={router} />)
  return action
}

/** What the form sent, as the action received it. */
async function sent(action: ActionSpy): Promise<FormData> {
  const asked = action.mock.calls[0]?.[0]
  if (!asked) throw new Error('the action was never reached')
  return asked.request.formData()
}

describe('AlbumFilters', () => {
  it('draws the album steps, on step three', async () => {
    showPage()

    expect(await screen.findByText('Filters')).toBeVisible()
    expect(screen.getByText('Prompt')).toBeVisible()
    expect(screen.queryByText('Dimensions')).not.toBeInTheDocument()
  })

  it('says when the selection came from the prompt', async () => {
    showPage()

    expect(
      await screen.findByText(
        'Pre-selected based on your prompt. Adjust if needed.',
      ),
    ).toBeVisible()
  })

  it('says nothing about a suggestion where there was none', async () => {
    showPage({ ...DATA, fromPrompt: false })

    await screen.findByRole('button', { name: /^Jazz/ })
    expect(
      screen.queryByText(/Pre-selected based on your prompt/),
    ).not.toBeInTheDocument()
  })

  it('marks the suggested genre and leaves the others alone', async () => {
    showPage()

    expect(
      await screen.findByRole('button', { name: /^Jazz/ }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /^Rock/ })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('offers the play-history preference as a radiogroup', async () => {
    showPage()

    const pills = await screen.findAllByRole('radio')
    expect(pills).toHaveLength(4)
    expect(pills[0]).toHaveAccessibleName('Any')
    expect(pills[0]).toHaveAttribute('aria-checked', 'true')
  })

  it('counts what the selection reaches', async () => {
    showPage()

    expect(
      await screen.findByText('900 albums (sending 500 to AI)'),
    ).toBeVisible()
  })

  it('caps the limit options at what the model can be sent', async () => {
    showPage({ ...DATA, ceiling: 2500 })

    expect(await screen.findByRole('button', { name: '1,000' })).toBeVisible()
    expect(
      screen.queryByRole('button', { name: '5,000' }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Max (2,500)' })).toBeVisible()
  })

  it('sends the selection, the totals and the two preferences', async () => {
    const action = showPage()

    await userEvent.click(await screen.findByRole('button', { name: /^Rock/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Something New' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Hidden gems' }))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    const form = await sent(action)
    expect(form.getAll('genres')).toEqual(['Jazz', 'Rock'])
    expect(form.get('genre_total')).toBe('2')
    expect(form.get('mode')).toBe('discovery')
    expect(form.get('familiarity')).toBe('hidden_gems')
  })

  it('selects and deselects every genre at once', async () => {
    showPage()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Select all genres' }),
    )

    expect(screen.getByRole('button', { name: /^Rock/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})
