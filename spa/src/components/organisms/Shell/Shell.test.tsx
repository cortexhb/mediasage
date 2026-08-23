import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { Shell } from './Shell.tsx'

/** The shell with one child page, so the outlet has something to render. */
function renderShell() {
  const router = createMemoryRouter([
    {
      Component: Shell,
      children: [{ index: true, Component: () => <h2>A page</h2> }],
    },
  ])
  return render(<RouterProvider router={router} />)
}

describe('Shell', () => {
  it('renders the page in its outlet', () => {
    renderShell()

    expect(screen.getByRole('heading', { name: 'A page' })).toBeVisible()
  })

  it('carries the navigation', () => {
    renderShell()

    expect(
      screen.getByRole('navigation', { name: 'Main navigation' }),
    ).toBeVisible()
  })

  it('points the logo home', () => {
    renderShell()

    expect(screen.getByRole('link', { name: 'MediaSage' })).toHaveAttribute(
      'href',
      '/',
    )
  })

  it('gives the skip link in index.html its target', () => {
    renderShell()

    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
  })
})
