import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { Nav } from './Nav.tsx'

/**
 * The nav under a router, at a path, with every path matching.
 *
 * The extra button is what an outside click lands on. Clicking a nav entry
 * would navigate, and the disclosure closes on navigation anyway, so the
 * assertion would hold whether or not outside clicks are handled.
 */
function renderNav(path = '/') {
  const Page = () => (
    <>
      <Nav />
      <button type="button">Elsewhere</button>
    </>
  )
  const router = createMemoryRouter([{ path: '*', Component: Page }], {
    initialEntries: [path],
  })
  return render(<RouterProvider router={router} />)
}

describe('Nav', () => {
  it('offers the entries the header carries', () => {
    renderNav()

    expect(screen.getByRole('button', { name: /Make Playlist/ })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Recommend Album' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Settings' })).toBeVisible()
  })

  describe('the playlist disclosure', () => {
    it('starts closed', () => {
      renderNav()

      expect(
        screen.getByRole('button', { name: /Make Playlist/ }),
      ).toHaveAttribute('aria-expanded', 'false')
      expect(
        screen.queryByRole('link', { name: 'From Prompt' }),
      ).not.toBeInTheDocument()
    })

    it('reveals both modes when opened', async () => {
      const user = userEvent.setup()
      renderNav()

      await user.click(screen.getByRole('button', { name: /Make Playlist/ }))

      expect(
        screen.getByRole('button', { name: /Make Playlist/ }),
      ).toHaveAttribute('aria-expanded', 'true')
      expect(screen.getByRole('link', { name: 'From Prompt' })).toBeVisible()
      expect(screen.getByRole('link', { name: 'From Seed Song' })).toBeVisible()
    })

    it('closes on Escape and hands focus back to the trigger', async () => {
      const user = userEvent.setup()
      renderNav()
      const trigger = screen.getByRole('button', { name: /Make Playlist/ })
      await user.click(trigger)

      await user.keyboard('{Escape}')

      expect(
        screen.queryByRole('link', { name: 'From Prompt' }),
      ).not.toBeInTheDocument()
      expect(trigger).toHaveFocus()
    })

    it('closes when the click lands outside it', async () => {
      const user = userEvent.setup()
      renderNav()
      await user.click(screen.getByRole('button', { name: /Make Playlist/ }))

      await user.click(screen.getByRole('button', { name: 'Elsewhere' }))

      expect(
        screen.queryByRole('link', { name: 'From Prompt' }),
      ).not.toBeInTheDocument()
    })

    it('closes when a mode is chosen', async () => {
      const user = userEvent.setup()
      renderNav()
      await user.click(screen.getByRole('button', { name: /Make Playlist/ }))

      await user.click(screen.getByRole('link', { name: 'From Prompt' }))

      expect(
        screen.queryByRole('link', { name: 'From Prompt' }),
      ).not.toBeInTheDocument()
    })

    it('checks the mode in use', async () => {
      const user = userEvent.setup()
      renderNav('/playlist/seed')

      await user.click(screen.getByRole('button', { name: /Make Playlist/ }))

      const seed = screen.getByRole('link', { name: 'From Seed Song' })
      expect(seed).toHaveAttribute('aria-current', 'page')
      // Decorative, so it is aria-hidden and not part of the name above.
      expect(within(seed).getByText('✓')).toBeVisible()
    })

    it('leaves the mode not in use unchecked', async () => {
      const user = userEvent.setup()
      renderNav('/playlist/seed')

      await user.click(screen.getByRole('button', { name: /Make Playlist/ }))

      expect(
        screen.getByRole('link', { name: 'From Prompt' }),
      ).not.toHaveAttribute('aria-current')
    })
  })

  describe('the current route', () => {
    it('marks the entry the page belongs to', () => {
      renderNav('/settings')

      expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute(
        'aria-current',
        'page',
      )
    })

    it('leaves the other entries unmarked', () => {
      renderNav('/settings')

      expect(
        screen.getByRole('link', { name: 'Recommend Album' }),
      ).not.toHaveAttribute('aria-current')
    })
  })
})
