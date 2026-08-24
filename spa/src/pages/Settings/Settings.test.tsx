import { render, screen, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { CONFIG, SETUP } from '@test'
import type { SettingsData } from '../../libs/loadSettings/loadSettings.ts'
import { SETTINGS_GROUPS } from '../../libs/settingsGroups/settingsGroups.ts'
import { Settings } from './Settings.tsx'

/** What a configured deployment loads. */
const DATA: SettingsData = { config: CONFIG, setup: SETUP, fields: [] }

/**
 * The layout on its own route, with the loader stubbed.
 *
 * The pane is a stub rather than `SettingsGroup`: what is asserted here is the
 * rail and the frame around it, and the real pane drags in a Plex sign-in.
 */
function renderPage(data: SettingsData = DATA, at = '/settings/plex') {
  const router = createMemoryRouter(
    [
      {
        path: '/settings',
        loader: () => data,
        Component: Settings,
        children: [{ path: ':group', Component: () => <p>the pane</p> }],
      },
    ],
    { initialEntries: [at] },
  )
  return render(<RouterProvider router={router} />)
}

describe('Settings', () => {
  it('titles itself under the shell heading', async () => {
    renderPage()

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Settings' }),
    ).toBeVisible()
  })

  it('offers every group, since each is the only way to reach its section', async () => {
    renderPage()

    const rail = await screen.findByRole('navigation', {
      name: 'Settings groups',
    })
    for (const group of SETTINGS_GROUPS) {
      expect(
        within(rail).getByRole('link', { name: group.title }),
      ).toBeInTheDocument()
    }
  })

  it('marks the group in force, so the rail says where you are', async () => {
    renderPage(DATA, '/settings/library')

    expect(
      await screen.findByRole('link', { name: 'Library' }),
    ).toHaveAttribute('aria-current', 'page')
  })

  it('draws the group under it', async () => {
    renderPage()

    expect(await screen.findByText('the pane')).toBeVisible()
  })

  it('says nothing about storage when the directory is writable', async () => {
    renderPage()

    await screen.findByText('the pane')
    expect(
      screen.queryByRole('heading', { name: 'Storage' }),
    ).not.toBeInTheDocument()
  })

  it('warns when it is not, above every group rather than inside one', async () => {
    renderPage({
      ...DATA,
      setup: {
        ...SETUP,
        data_dir_writable: false,
        data_dir: '/data',
        process_uid: 1000,
        process_gid: 1000,
      },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '/data is not writable',
    )
  })
})
