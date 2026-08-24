import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { SETTINGS_GROUPS } from '../../../libs/settingsGroups/settingsGroups.ts'
import { SettingsRail } from './SettingsRail.tsx'

/** The rail on the layout route, which is what its links are relative to. */
function renderRail(at = '/settings/plex') {
  const router = createMemoryRouter(
    [
      {
        path: '/settings',
        Component: SettingsRail,
        children: [{ path: ':group', Component: () => null }],
      },
    ],
    { initialEntries: [at] },
  )
  return render(<RouterProvider router={router} />)
}

describe('SettingsRail', () => {
  it('offers every group, since each is the only way to reach its sections', () => {
    renderRail()

    for (const group of SETTINGS_GROUPS) {
      expect(screen.getByRole('link', { name: group.title })).toBeVisible()
    }
  })

  it('points each link at that group under settings', () => {
    renderRail()

    expect(screen.getByRole('link', { name: 'Library' })).toHaveAttribute(
      'href',
      '/settings/library',
    )
  })

  it('marks the group in force, so the rail says where you are', () => {
    renderRail('/settings/advanced')

    expect(screen.getByRole('link', { name: 'Advanced' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('marks only that one', () => {
    renderRail('/settings/advanced')

    expect(screen.getByRole('link', { name: 'Plex' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('names itself, since a page carries more than one navigation', () => {
    renderRail()

    expect(
      screen.getByRole('navigation', { name: 'Settings groups' }),
    ).toBeVisible()
  })
})
