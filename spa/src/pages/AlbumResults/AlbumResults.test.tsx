import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Mock } from 'vitest'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  AlbumRecommendation,
  RecommendResultFrame,
} from '../../api/generated/types.gen.ts'
import { forgetRound } from '../../libs/albumRun/albumRun.ts'
import type { AlbumFlow } from '../../libs/albumStore/albumStore.ts'
import { AlbumResults } from './AlbumResults.tsx'

/** The route's action, stubbed, so a submit is read rather than followed. */
type ActionSpy = Mock<(args: { request: Request }) => null>

const PRIMARY: AlbumRecommendation = {
  rank: 'primary',
  album: 'Pink Moon',
  artist: 'Nick Drake',
  year: 1972,
  track_rating_keys: ['1', '2'],
  pitch: {
    hook: 'Twenty-eight minutes, one guitar.',
    context: 'Recorded in two nights.',
    listening_guide: 'Start at the title track.',
    connection: 'It matches the rain you asked for.',
    full_text: 'the whole pitch',
  },
}

const SECONDARY: AlbumRecommendation = {
  rank: 'secondary',
  album: 'Bryter Layter',
  artist: 'Nick Drake',
  track_rating_keys: ['3'],
  pitch: { short_pitch: 'The warm one.' },
}

const RESULT: RecommendResultFrame = {
  recommendations: [PRIMARY, SECONDARY],
  token_count: 12,
  estimated_cost: 0,
  result_id: 'r-1',
}

const FLOW: AlbumFlow = {
  id: 'f-1',
  sessionId: 's-1',
  prompt: 'rainy Sunday',
  questions: [],
  answers: [],
  answerTexts: [],
  mode: 'library',
  familiarity: 'any',
  filters: { genres: [], decades: [], max_albums: 2500 },
  result: RESULT,
}

/** The page on its own route, with the loader stubbed and the action spied. */
function showPage(
  flow: AlbumFlow = FLOW,
  action: ActionSpy = vi.fn(() => null),
): ActionSpy {
  const router = createMemoryRouter(
    [
      {
        path: '/recommend/results',
        loader: () => flow,
        action,
        Component: AlbumResults,
      },
    ],
    { initialEntries: ['/recommend/results'] },
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

describe('AlbumResults', () => {
  afterEach(forgetRound)

  it('redraws the round kept in the record, without generating one', async () => {
    showPage()

    expect(await screen.findByText('Pink Moon')).toBeVisible()
    expect(screen.getByText('Nick Drake (1972)')).toBeVisible()
  })

  it('draws the four parts of the pitch under their own labels', async () => {
    showPage()

    expect(await screen.findByText('The Story')).toBeVisible()
    expect(screen.getByText('How to Listen')).toBeVisible()
    expect(screen.getByText('Why This Album')).toBeVisible()
    expect(screen.getByText('Twenty-eight minutes, one guitar.')).toBeVisible()
  })

  it('draws no stepper, as the legacy hides it on this step', async () => {
    showPage()

    await screen.findByText('Pink Moon')
    expect(screen.queryByLabelText('Progress')).not.toBeInTheDocument()
  })

  it('lists the other picks with their one-line pitch', async () => {
    showPage()

    expect(await screen.findByText('Also worth exploring')).toBeVisible()
    expect(screen.getByText('The warm one.')).toBeVisible()
  })

  it('sends the album the save button belongs to', async () => {
    const action = showPage()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Save to Playlist' }),
    )

    const form = await sent(action)
    expect(form.get('intent')).toBe('save')
    expect(form.get('album')).toBe('Pink Moon')
    expect(form.getAll('rating_keys')).toEqual(['1', '2'])
    expect(form.get('pitch')).toBe('the whole pitch')
  })

  it('asks for another round on the same session', async () => {
    const action = showPage()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Show Me Another' }),
    )

    expect((await sent(action)).get('intent')).toBe('again')
  })

  it('offers the discovery bridge in library mode', async () => {
    const action = showPage()

    await userEvent.click(
      await screen.findByRole('button', {
        name: 'Recommend something not in my library',
      }),
    )

    expect((await sent(action)).get('intent')).toBe('discovery')
  })

  it('offers no bridge once the session is already discovering', async () => {
    showPage({ ...FLOW, mode: 'discovery' })

    await screen.findByText('Pink Moon')
    expect(
      screen.queryByRole('button', {
        name: 'Recommend something not in my library',
      }),
    ).not.toBeInTheDocument()
  })

  it('warns when the pitch could not be fully grounded', async () => {
    showPage({
      ...FLOW,
      result: { ...RESULT, research_warning: 'Research was unavailable' },
    })

    expect(await screen.findByText('Research was unavailable')).toBeVisible()
  })

  it('offers nothing to play for an album that is not in the library', async () => {
    showPage({
      ...FLOW,
      result: {
        ...RESULT,
        recommendations: [{ ...PRIMARY, track_rating_keys: [] }],
      },
    })

    await screen.findByText('Pink Moon')
    expect(
      screen.queryByRole('button', { name: '▶ Play Now' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Show Me Another' }),
    ).toBeVisible()
  })
})
