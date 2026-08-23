import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Input } from './Input.tsx'

describe('Input', () => {
  it('takes what is typed into it', async () => {
    const user = userEvent.setup()
    render(<Input aria-label="Plex Server URL" />)

    await user.type(screen.getByRole('textbox'), 'http://plex:32400')

    expect(screen.getByRole('textbox')).toHaveValue('http://plex:32400')
  })

  it('passes its attributes through', () => {
    render(<Input type="password" name="plex_token" aria-label="Plex Token" />)

    const input = screen.getByLabelText('Plex Token')
    expect(input).toHaveAttribute('type', 'password')
    expect(input).toHaveAttribute('name', 'plex_token')
  })

  it('starts on the value it was given', () => {
    render(<Input defaultValue="Music" aria-label="Music Library" />)

    expect(screen.getByRole('textbox')).toHaveValue('Music')
  })

  it('disables itself when told to', () => {
    // Set on a value the deployment supplies through the environment.
    render(<Input disabled aria-label="Provider" />)

    expect(screen.getByRole('textbox')).toBeDisabled()
  })
})
