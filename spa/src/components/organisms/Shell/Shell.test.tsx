import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import { Shell } from './Shell.tsx'

/** A synced library, so the footer's poller has something to report. */
const SYNCED = {
  track_count: 1200,
  synced_at: '2026-08-23T09:00:00Z',
  is_syncing: false,
  plex_connected: true,
}

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
  beforeEach(() => {
    server.use(http.get('/api/library/status', () => HttpResponse.json(SYNCED)))
  })

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

  it('carries the footer, so the sync state is on every page', async () => {
    renderShell()

    expect(await screen.findByText('1,200 tracks')).toBeVisible()
  })
})
