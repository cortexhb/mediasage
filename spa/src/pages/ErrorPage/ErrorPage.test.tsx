import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { ErrorPage } from './ErrorPage.tsx'

/** A route whose loader throws, so the boundary renders for real. */
function renderThrowing(thrown: unknown) {
  const router = createMemoryRouter([
    {
      path: '/',
      Component: () => <p>Never rendered</p>,
      loader: () => {
        throw thrown
      },
      ErrorBoundary: ErrorPage,
    },
  ])
  return render(<RouterProvider router={router} />)
}

describe('ErrorPage', () => {
  it('says what went wrong, taking the message off the error', async () => {
    renderThrowing(new Error('Plex refused the token'))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Plex refused the token',
    )
  })

  it('reports the status line when a loader threw a Response', async () => {
    renderThrowing(new Response(null, { status: 503, statusText: 'No API' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('503 No API')
  })

  it('still renders for something thrown that explains nothing', async () => {
    renderThrowing('a bare string')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The page could not be loaded.',
    )
  })

  it('says what to do about it', async () => {
    renderThrowing(new Error('boom'))

    expect(
      await screen.findByRole('heading', { name: 'Something went wrong' }),
    ).toBeVisible()
    expect(
      screen.getByText('Reload the page, or check that the API is up.'),
    ).toBeVisible()
  })
})
