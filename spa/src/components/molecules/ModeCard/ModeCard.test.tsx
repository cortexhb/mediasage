import { render as mount, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { ModeCardProps } from './ModeCard.tsx'
import { ModeCard } from './ModeCard.tsx'

const PROPS: ModeCardProps = {
  to: '/playlist/prompt',
  mode: 'prompt_playlist',
  title: 'Playlist from Prompt',
  description: 'Describe a vibe and let AI curate tracks',
}

/** The card inside a router, since it is a link. */
function render(props: Partial<ModeCardProps> = {}) {
  const router = createMemoryRouter([
    { index: true, Component: () => <ModeCard {...PROPS} {...props} /> },
    { path: 'playlist/prompt', Component: () => <p>Prompt step</p> },
  ])
  return mount(<RouterProvider router={router} />)
}

/** The card itself, found the way a reader finds it. */
function card(): HTMLElement {
  return screen.getByRole('link', { name: /Playlist from Prompt/ })
}

describe('ModeCard', () => {
  it('is a link, so it opens in a new tab', () => {
    // `frontend/index.html:186` drew these as buttons behind a click handler.
    render()

    expect(card()).toHaveAttribute('href', '/playlist/prompt')
  })

  it('names what it makes and what that means', () => {
    render()

    expect(
      screen.getByText('Describe a vibe and let AI curate tracks'),
    ).toBeVisible()
  })

  it('goes where it points', async () => {
    render()

    await userEvent.click(card())

    expect(await screen.findByText('Prompt step')).toBeVisible()
  })

  describe('when disabled', () => {
    it('says so, rather than only looking dimmed', () => {
      render({ disabled: true })

      expect(card()).toHaveAttribute('aria-disabled', 'true')
    })

    it('stays a link, so a keyboard still finds and hears it', () => {
      // Dropping `to` would leave the tab order and the link role.
      render({ disabled: true })

      expect(card()).toHaveAttribute('href', '/playlist/prompt')
    })

    it('does not navigate when clicked', async () => {
      render({ disabled: true })

      await userEvent.click(card())

      expect(screen.queryByText('Prompt step')).not.toBeInTheDocument()
    })

    it('is enabled unless the caller says otherwise', () => {
      render()

      expect(card()).toHaveAttribute('aria-disabled', 'false')
    })
  })
})
