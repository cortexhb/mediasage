import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Mock } from 'vitest'
import { describe, expect, it, vi } from 'vitest'

import type { Track } from '../../api/generated/types.gen.ts'
import type { ResultDetail } from '../../api/results/results.ts'
import { Result } from './Result.tsx'

/** The route's action, stubbed, so a submit is read rather than followed. */
type ActionSpy = Mock<(args: { request: Request }) => null>

const TRACK: Track = {
  rating_key: '1',
  title: 'Pink Moon',
  artist: 'Nick Drake',
  album: 'Pink Moon',
  duration_ms: 121_000,
}

const OTHER: Track = {
  rating_key: '2',
  title: 'Road',
  artist: 'Nick Drake',
  album: 'Pink Moon',
  duration_ms: 121_000,
}

const PLAYLIST: ResultDetail = {
  id: 'r-1',
  title: 'Rainy Sunday',
  prompt: 'something for a rainy Sunday',
  track_count: 2,
  created_at: '2026-08-01T10:00:00Z',
  type: 'prompt_playlist',
  snapshot: {
    tracks: [TRACK, OTHER],
    token_count: 900,
    estimated_cost: 0.01,
    playlist_title: 'Rainy Sunday',
    narrative: 'Quiet guitars for a grey afternoon.',
    track_reasons: { '1': 'It opens the record.' },
  },
}

const ALBUM: ResultDetail = {
  id: 'r-2',
  title: 'Pink Moon',
  prompt: 'rainy Sunday',
  track_count: 11,
  created_at: '2026-08-01T10:00:00Z',
  type: 'album_recommendation',
  snapshot: {
    recommendations: [
      {
        rank: 'primary',
        album: 'Pink Moon',
        artist: 'Nick Drake',
        year: 1972,
        track_rating_keys: ['1', '2'],
        pitch: { hook: 'Twenty-eight minutes, one guitar.' },
      },
      {
        rank: 'secondary',
        album: 'Bryter Layter',
        artist: 'Nick Drake',
        track_rating_keys: ['3'],
        pitch: { short_pitch: 'The warm one.' },
      },
    ],
    token_count: 12,
    estimated_cost: 0,
  },
}

/** The page on its own route, with the loader stubbed and the action spied. */
function showPage(
  detail: ResultDetail,
  action: ActionSpy = vi.fn(() => null),
): ActionSpy {
  const router = createMemoryRouter(
    [
      {
        path: '/result/:resultId',
        loader: () => detail,
        action,
        Component: Result,
      },
    ],
    { initialEntries: [`/result/${detail.id}`] },
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

describe('Result', () => {
  describe('a saved playlist', () => {
    it('draws the snapshot, not a generated run', async () => {
      showPage(PLAYLIST)

      expect(await screen.findByText('Road')).toBeVisible()
      expect(
        screen.getByText('Quiet guitars for a grey afternoon.'),
      ).toBeVisible()
    })

    it('offers the stored title as the name to save under', async () => {
      showPage(PLAYLIST)

      expect(await screen.findByLabelText('Playlist name')).toHaveValue(
        'Rainy Sunday',
      )
    })

    it('quotes the request that produced it', async () => {
      showPage(PLAYLIST)

      expect(
        await screen.findByText('something for a rainy Sunday'),
      ).toBeVisible()
    })

    it('counts the tracks it holds', async () => {
      showPage(PLAYLIST)

      expect(await screen.findByText('♫ 2 tracks')).toBeVisible()
    })

    it('shows the first track reason until another is chosen', async () => {
      showPage(PLAYLIST)

      expect(await screen.findByText('It opens the record.')).toBeVisible()
    })

    it('sends every track key to the save', async () => {
      const action = showPage(PLAYLIST)
      await screen.findByText('Road')

      await userEvent.click(
        screen.getByRole('button', { name: 'Save to Plex' }),
      )

      const form = await sent(action)
      expect(form.getAll('rating_keys')).toEqual(['1', '2'])
      expect(form.get('name')).toBe('Rainy Sunday')
    })

    it('offers nothing that would need a session behind it', async () => {
      showPage(PLAYLIST)
      await screen.findByText('Road')

      expect(screen.queryByText('Start over')).not.toBeInTheDocument()
      expect(screen.queryByText('← Back to filters')).not.toBeInTheDocument()
    })
  })

  describe('a saved recommendation', () => {
    it('draws the album it recommended', async () => {
      showPage(ALBUM)

      expect(await screen.findByText('Pink Moon')).toBeVisible()
      expect(screen.getByText('Nick Drake (1972)')).toBeVisible()
    })

    it('lists the other picks', async () => {
      showPage(ALBUM)

      expect(await screen.findByText('Also worth exploring')).toBeVisible()
      expect(screen.getByText('The warm one.')).toBeVisible()
    })

    it('saves an album by what the form carries, not by a session', async () => {
      const action = showPage(ALBUM)
      await screen.findByText('Also worth exploring')

      await userEvent.click(
        screen.getByRole('button', { name: 'Save to Playlist' }),
      )

      const form = await sent(action)
      expect(form.get('intent')).toBe('album')
      expect(form.get('album')).toBe('Pink Moon')
      expect(form.getAll('rating_keys')).toEqual(['1', '2'])
    })

    it('offers no way to buy another round', async () => {
      showPage(ALBUM)
      await screen.findByText('Also worth exploring')

      expect(screen.queryByText('Show Me Another')).not.toBeInTheDocument()
      expect(screen.queryByText('Start over')).not.toBeInTheDocument()
    })
  })
})
