import { render as mount, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { PlexSettingsProps } from './PlexSettings.tsx'
import { PlexSettings } from './PlexSettings.tsx'

/** A connected server with a token stored and nothing set by the environment. */
const PROPS = {
  url: 'http://plex:32400',
  library: 'Music',
  connected: true,
  tokenSet: true,
  fromEnv: false,
  libraries: ['Music'],
}

/** What a synced library reports, on the route the card's counts fetch. */
const STATS = {
  total_tracks: 52341,
  genres: [{ name: 'Rock', count: 900 }],
  decades: [{ name: '1980s', count: 620 }],
}

/** The card inside a router, since its counts come from a resource route. */
function render(props: PlexSettingsProps) {
  const router = createMemoryRouter([
    { index: true, Component: () => <PlexSettings {...props} /> },
    { path: 'settings/stats', loader: () => STATS },
  ])
  return mount(<RouterProvider router={router} />)
}

describe('PlexSettings', () => {
  it.each([
    [true, 'Connected'],
    [false, 'Not connected'],
  ])('reports connected=%s as "%s"', (connected, reported) => {
    render({ ...PROPS, connected })

    expect(screen.getByRole('status')).toHaveTextContent(reported)
  })

  it('shows the saved server address', () => {
    render({ ...PROPS })

    expect(
      screen.getByRole('textbox', { name: 'Plex Server URL' }),
    ).toHaveValue('http://plex:32400')
  })

  describe('the token field', () => {
    it('starts empty, so a submit does not resend the stored value', () => {
      render({ ...PROPS })

      expect(screen.getByLabelText('Plex Token')).toHaveValue('')
    })

    it('says that leaving it blank keeps what is stored', () => {
      render({ ...PROPS })

      expect(screen.getByLabelText('Plex Token')).toHaveAccessibleDescription(
        'Leave blank to keep the stored token.',
      )
    })

    it('marks a stored token in the placeholder, since the value cannot be read', () => {
      render({ ...PROPS, tokenSet: true })

      expect(
        screen.getByLabelText('Plex Token').getAttribute('placeholder'),
      ).toContain('(configured)')
    })

    it('asks for one when none is stored', () => {
      render({ ...PROPS, tokenSet: false })

      expect(screen.getByLabelText('Plex Token')).toHaveAttribute(
        'placeholder',
        'Your Plex token',
      )
    })
  })

  describe('when the deployment supplies the connection', () => {
    it('shows the values but refuses edits, so what is in force is visible', () => {
      render({ ...PROPS, fromEnv: true })

      expect(
        screen.getByRole('textbox', { name: 'Plex Server URL' }),
      ).toBeDisabled()
      expect(screen.getByLabelText('Plex Token')).toBeDisabled()
    })

    it('says where to change them', () => {
      render({ ...PROPS, fromEnv: true })

      expect(
        screen.getByRole('textbox', { name: 'Plex Server URL' }),
      ).toHaveAccessibleDescription(
        'Set by the environment. Edit .env to change.',
      )
    })
  })

  it('leaves the library to LibraryField', () => {
    render({ ...PROPS, libraries: ['Music', 'Vinyl'] })

    expect(screen.getByRole('combobox', { name: 'Music Library' })).toHaveValue(
      'Music',
    )
  })

  it('reports the counts here, under the fields that decide them', async () => {
    render({ ...PROPS })

    expect(await screen.findByText('Total Tracks')).toBeVisible()
    expect(screen.getByText('52,341')).toBeVisible()
  })
})
