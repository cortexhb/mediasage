import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Mock } from 'vitest'
import { describe, expect, it, vi } from 'vitest'

import type { SeedFlow } from '../../libs/flowStore/flowStore.ts'
import { DimensionsStep } from './DimensionsStep.tsx'

/** The route's action, stubbed, so a submit is read rather than followed. */
type ActionSpy = Mock<(args: { request: Request }) => null>

const FLOW: SeedFlow = {
  mode: 'seed',
  id: 'f-1',
  track: {
    rating_key: '99',
    title: 'Fake Plastic Trees',
    artist: 'Radiohead',
    album: 'The Bends',
    duration_ms: 290_000,
  },
  dimensions: [
    { id: 'mood', label: 'Mood', description: 'How it feels' },
    { id: 'era', label: 'Era', description: 'When it is from' },
  ],
}

/** The page on its own route, with the loader stubbed and the action spied. */
function showPage(
  flow: SeedFlow = FLOW,
  action: ActionSpy = vi.fn(() => null),
): ActionSpy {
  const router = createMemoryRouter(
    [
      {
        path: '/playlist/seed/dimensions',
        loader: () => flow,
        action,
        Component: DimensionsStep,
      },
    ],
    { initialEntries: ['/playlist/seed/dimensions'] },
  )
  render(<RouterProvider router={router} />)
  return action
}

/** One dimension card, once the router has hydrated the page. */
function card(name: RegExp | string): Promise<HTMLElement> {
  return screen.findByRole('checkbox', { name })
}

/** What the form sent, as the action received it. */
async function sent(action: ActionSpy): Promise<FormData> {
  const asked = action.mock.calls[0]?.[0]
  if (!asked) throw new Error('the action was never reached')
  return asked.request.formData()
}

describe('DimensionsStep', () => {
  it('names the track everything is picked to sound like', async () => {
    showPage()

    expect(await screen.findByText('Fake Plastic Trees')).toBeVisible()
    expect(screen.getByText('Radiohead - The Bends')).toBeVisible()
  })

  it('offers each dimension as a checkbox, none chosen', async () => {
    showPage()

    const cards = await screen.findAllByRole('checkbox')
    expect(cards).toHaveLength(2)
    expect(cards[0]).toHaveAccessibleName('Mood: How it feels')
    expect(cards[0]).toHaveAttribute('aria-checked', 'false')
  })

  it('marks one chosen when it is clicked, and unmarks it again', async () => {
    showPage()
    const mood = await card('Mood: How it feels')

    await userEvent.click(mood)
    expect(mood).toHaveAttribute('aria-checked', 'true')

    await userEvent.click(mood)
    expect(mood).toHaveAttribute('aria-checked', 'false')
  })

  it('toggles from the keyboard, as the legacy card did', async () => {
    showPage()
    const mood = await card('Mood: How it feels')

    mood.focus()
    await userEvent.keyboard(' ')

    expect(mood).toHaveAttribute('aria-checked', 'true')
  })

  it('sends the chosen ids and the notes', async () => {
    const action = showPage()

    await userEvent.click(await card(/^Era/))
    await userEvent.type(
      screen.getByLabelText(/Additional notes/),
      'no ballads',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Continue to Filters' }),
    )

    const form = await sent(action)
    expect(form.getAll('dimensions')).toEqual(['era'])
    expect(form.get('notes')).toBe('no ballads')
  })

  it('redraws what an earlier visit chose', async () => {
    showPage({ ...FLOW, selectedDimensions: ['era'] })

    expect(await card(/^Era/)).toHaveAttribute('aria-checked', 'true')
  })
})
