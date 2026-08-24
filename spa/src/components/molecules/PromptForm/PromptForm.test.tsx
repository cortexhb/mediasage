import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { Mock } from 'vitest'
import { describe, expect, it, vi } from 'vitest'

import { PromptForm } from './PromptForm.tsx'

/** The route's action, stubbed, so a submit is read rather than followed. */
type ActionSpy = Mock<(args: { request: Request }) => null>

const GROUPS = [
  ['rainy afternoon', 'sunny drive'],
  ['deep focus', 'late night'],
]

const STAGES = ['Parsing your request...']

/** The form on a route of its own, with the action spied. */
function showForm(
  error?: string,
  action: ActionSpy = vi.fn(() => null),
): ActionSpy {
  const router = createMemoryRouter(
    [
      {
        path: '/',
        action,
        Component: () => (
          <PromptForm
            steps={['Prompt', 'Refine', 'Filters', 'Results']}
            heading="Describe your playlist"
            blurb="Tell us what you are in the mood for."
            placeholder="e.g., melancholy 90s alternative..."
            label="Playlist description"
            groups={GROUPS}
            submitLabel="Analyze"
            error={error}
            waitLabel="Reading your prompt"
            stages={STAGES}
          />
        ),
      },
    ],
    { initialEntries: ['/'] },
  )
  render(<RouterProvider router={router} />)
  return action
}

describe('PromptForm', () => {
  it('offers one suggestion per group, so the row spans them', () => {
    showForm()

    const shown = GROUPS.map((group) =>
      group.filter((suggestion) => screen.queryByText(suggestion) !== null),
    )
    expect(shown.map((each) => each.length)).toEqual([1, 1])
  })

  it('puts a suggestion in the box rather than submitting it', async () => {
    const action = showForm()
    const suggestion =
      GROUPS[0]?.find((each) => screen.queryByText(each) !== null) ?? ''

    await userEvent.click(screen.getByText(suggestion))

    expect(screen.getByLabelText('Playlist description')).toHaveValue(
      suggestion,
    )
    expect(action).not.toHaveBeenCalled()
  })

  it('shuffles to a suggestion the reader has not just seen', async () => {
    showForm()
    const before = GROUPS.flat().filter(
      (suggestion) => screen.queryByText(suggestion) !== null,
    )

    await userEvent.click(
      screen.getByRole('button', { name: 'Show different suggestions' }),
    )

    const after = GROUPS.flat().filter(
      (suggestion) => screen.queryByText(suggestion) !== null,
    )
    expect(after).not.toEqual(before)
  })

  it('submits what was typed', async () => {
    const action = showForm()

    await userEvent.type(
      screen.getByLabelText('Playlist description'),
      'something loud',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Analyze' }))

    expect(action).toHaveBeenCalledOnce()
    const request = action.mock.calls[0]?.[0].request
    const form = await request?.formData()
    expect(form?.get('prompt')).toBe('something loud')
  })

  it('announces what the action answered', () => {
    showForm('The model is not configured')

    expect(screen.getByRole('alert')).toHaveTextContent(
      'The model is not configured',
    )
  })
})
