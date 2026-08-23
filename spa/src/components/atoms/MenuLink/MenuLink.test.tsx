import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { MenuLink } from './MenuLink.tsx'

/** The link under a router, at a path, with every path matching. */
function renderLink(path: string, onChoose?: () => void) {
  const Page = () => (
    <MenuLink to="/here" {...(onChoose && { onChoose })}>
      Go here
    </MenuLink>
  )
  const router = createMemoryRouter([{ path: '*', Component: Page }], {
    initialEntries: [path],
  })
  return render(<RouterProvider router={router} />)
}

describe('MenuLink', () => {
  it('links to where it was pointed', () => {
    renderLink('/elsewhere')

    expect(screen.getByRole('link', { name: 'Go here' })).toHaveAttribute(
      'href',
      '/here',
    )
  })

  it('marks itself when its route is the open one', () => {
    renderLink('/here')

    expect(screen.getByRole('link', { name: 'Go here' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('stays unmarked on any other route', () => {
    renderLink('/elsewhere')

    expect(screen.getByRole('link', { name: 'Go here' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('checks itself when its route is the open one', () => {
    renderLink('/here')

    const link = screen.getByRole('link', { name: 'Go here' })
    // Decorative, so it is aria-hidden and absent from the name above.
    expect(within(link).getByText('✓')).toBeVisible()
  })

  it('shows no checkmark on any other route', () => {
    renderLink('/elsewhere')

    expect(within(screen.getByRole('link')).queryByText('✓')).toBeNull()
  })

  it('reports being chosen', async () => {
    const onChoose = vi.fn()
    const user = userEvent.setup()
    renderLink('/elsewhere', onChoose)

    await user.click(screen.getByRole('link', { name: 'Go here' }))

    expect(onChoose).toHaveBeenCalledOnce()
  })
})
