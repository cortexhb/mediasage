import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { routes } from './routes.ts'

/** The real route table, entered at a path. */
function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(<RouterProvider router={router} />)
}

describe('routes', () => {
  it('answers an unmatched path with the not-found page', () => {
    renderAt('/nowhere')

    expect(
      screen.getByRole('heading', { name: 'Page not found' }),
    ).toBeVisible()
  })

  it('keeps the shell around a not-found page', () => {
    // The header is how a wrong address is recoverable without the back
    // button.
    renderAt('/nowhere')

    expect(
      screen.getByRole('navigation', { name: 'Main navigation' }),
    ).toBeVisible()
  })

  it('answers a route that has not been built yet', () => {
    // Every navigation entry points at one of these until its phase lands.
    renderAt('/settings')

    expect(
      screen.getByRole('heading', { name: 'Page not found' }),
    ).toBeVisible()
  })
})
