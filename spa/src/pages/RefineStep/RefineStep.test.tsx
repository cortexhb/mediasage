import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Mock } from 'vitest'
import { describe, expect, it, vi } from 'vitest'

import type { PromptFlow } from '../../libs/flowStore/flowStore.ts'
import { RefineStep } from './RefineStep.tsx'

/** The route's action, stubbed, so a submit is read rather than followed. */
type ActionSpy = Mock<(args: { request: Request }) => null>

const FLOW: PromptFlow = {
  mode: 'prompt',
  id: 'f-1',
  prompt: 'moody jazz',
  questions: [
    {
      dimension: 'mood',
      question_text: 'How heavy?',
      options: ['Light', 'Heavy'],
    },
  ],
}

/** The page on its own route, with the loader stubbed and the action spied. */
function showPage(action: ActionSpy = vi.fn(() => null)): ActionSpy {
  const router = createMemoryRouter(
    [
      {
        path: '/playlist/prompt/refine',
        loader: () => FLOW,
        action,
        Component: RefineStep,
      },
    ],
    { initialEntries: ['/playlist/prompt/refine'] },
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

describe('RefineStep', () => {
  it('sends the chosen option and the detail', async () => {
    const action = showPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Heavy' }))
    await userEvent.type(
      screen.getByLabelText('Your own detail for: How heavy?'),
      'no drums',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    const form = await sent(action)
    expect(form.get('option-0')).toBe('Heavy')
    expect(form.get('detail-0')).toBe('no drums')
  })

  it('clears both halves when a question is skipped', async () => {
    // Skipping sets the answer and the detail in one handler; a non-functional
    // update let the second overwrite the first, keeping the chosen option.
    const action = showPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Heavy' }))
    await userEvent.type(
      screen.getByLabelText('Your own detail for: How heavy?'),
      'no drums',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Skip this question' }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    const form = await sent(action)
    expect(form.get('option-0')).toBe('')
    expect(form.get('detail-0')).toBe('')
  })
})
