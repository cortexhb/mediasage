import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Mock } from 'vitest'
import { describe, expect, it, vi } from 'vitest'

import type { SeedSearchData } from '../../libs/loadSeedSearch/loadSeedSearch.ts'
import { SeedStep } from './SeedStep.tsx'

/** The route's action, stubbed, so a pick is read rather than followed. */
type ActionSpy = Mock<(args: { request: Request }) => null>

const TRACKS = [
  {
    rating_key: '99',
    title: 'Fake Plastic Trees',
    artist: 'Radiohead',
    album: 'The Bends',
    duration_ms: 290_000,
  },
  {
    rating_key: '100',
    title: 'Pink Moon',
    artist: 'Nick Drake',
    album: 'Pink Moon',
    duration_ms: 120_000,
  },
]

const FOUND: SeedSearchData = { query: 'radiohead', tracks: TRACKS }

/** The page on its own route, with the loader stubbed and the action spied. */
function showPage(
  data: SeedSearchData = FOUND,
  action: ActionSpy = vi.fn(() => null),
): ActionSpy {
  const router = createMemoryRouter(
    [
      {
        path: '/playlist/seed',
        loader: () => data,
        action,
        Component: SeedStep,
      },
    ],
    { initialEntries: ['/playlist/seed'] },
  )
  render(<RouterProvider router={router} />)
  return action
}

/** The search box, once the router has hydrated the page. */
function box(): Promise<HTMLElement> {
  return screen.findByLabelText('Search for tracks')
}

describe('SeedStep', () => {
  it('draws the seed steps rather than the prompt ones', async () => {
    showPage()

    expect(await screen.findByText('Seed')).toBeVisible()
    expect(screen.getByText('Dimensions')).toBeVisible()
    expect(screen.queryByText('Refine')).not.toBeInTheDocument()
  })

  it('lists what the search found, with artist and album', async () => {
    showPage()

    const results = await screen.findAllByRole('option')
    expect(results).toHaveLength(2)
    expect(results[0]).toHaveAccessibleName('Fake Plastic Trees by Radiohead')
    expect(screen.getByText('Radiohead - The Bends')).toBeVisible()
  })

  it('keeps the box filled with what was searched for', async () => {
    showPage()

    expect(await box()).toHaveValue('radiohead')
  })

  it('sends the picked track to the action', async () => {
    const action = showPage()

    await userEvent.click(
      await screen.findByRole('option', { name: 'Pink Moon by Nick Drake' }),
    )

    expect(action).toHaveBeenCalledOnce()
    const asked = action.mock.calls[0]?.[0]
    if (!asked) throw new Error('the action was never reached')
    expect((await asked.request.formData()).get('rating_key')).toBe('100')
  })

  it('says so when a search found nothing', async () => {
    showPage({ query: 'zzzz', tracks: [] })

    expect(await screen.findByText('No tracks found')).toBeVisible()
  })

  it('draws no empty message before anything was searched for', async () => {
    showPage({ query: '', tracks: [] })

    await box()
    expect(screen.queryByText('No tracks found')).not.toBeInTheDocument()
  })

  it('reports a failed search without losing the query', async () => {
    showPage({ query: 'jazz', tracks: [], error: 'Not connected to Plex' })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Not connected to Plex',
    )
    expect(await box()).toHaveValue('jazz')
  })
})
