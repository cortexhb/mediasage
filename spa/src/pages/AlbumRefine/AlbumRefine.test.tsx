import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Mock } from 'vitest'
import { describe, expect, it, vi } from 'vitest'

import type { AlbumFlow } from '../../libs/albumStore/albumStore.ts'
import { AlbumRefine } from './AlbumRefine.tsx'

/** The route's action, stubbed, so a submit is read rather than followed. */
type ActionSpy = Mock<(args: { request: Request }) => null>

const FLOW: AlbumFlow = {
  id: 'f-1',
  sessionId: 's-1',
  prompt: 'rainy Sunday',
  questions: [
    {
      dimension: 'mood',
      question_text: 'How heavy?',
      options: ['Light', 'Heavy'],
    },
  ],
  mode: 'library',
  familiarity: 'any',
}

/** The page on its own route, with the loader stubbed and the action spied. */
function showPage(action: ActionSpy = vi.fn(() => null)): ActionSpy {
  const router = createMemoryRouter(
    [
      {
        path: '/recommend/refine',
        loader: () => FLOW,
        action,
        Component: AlbumRefine,
      },
    ],
    { initialEntries: ['/recommend/refine'] },
  )
  render(<RouterProvider router={router} />)
  return action
}

describe('AlbumRefine', () => {
  it('draws the album steps, on step two', async () => {
    showPage()

    expect(await screen.findByText('Refine')).toBeVisible()
    expect(screen.getByText('Prompt')).toBeVisible()
  })

  it('sends the chosen option and the detail as separate fields', async () => {
    const action = showPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Heavy' }))
    await userEvent.type(
      screen.getByLabelText('Your own detail for: How heavy?'),
      'no drums',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    const asked = action.mock.calls[0]?.[0]
    if (!asked) throw new Error('the action was never reached')
    const form = await asked.request.formData()
    expect(form.get('option-0')).toBe('Heavy')
    expect(form.get('detail-0')).toBe('no drums')
  })

  it('sends an empty option for a question that was skipped', async () => {
    const action = showPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Heavy' }))
    await userEvent.click(
      screen.getByRole('button', { name: 'Skip this question' }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    const asked = action.mock.calls[0]?.[0]
    if (!asked) throw new Error('the action was never reached')
    expect((await asked.request.formData()).get('option-0')).toBe('')
  })
})
