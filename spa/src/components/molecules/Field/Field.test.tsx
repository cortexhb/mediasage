import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Field } from './Field.tsx'

describe('Field', () => {
  it('labels its input', () => {
    render(<Field label="Plex Server URL" />)

    expect(screen.getByLabelText('Plex Server URL')).toBeVisible()
  })

  it('gives each field its own label association', () => {
    render(
      <>
        <Field label="First" />
        <Field label="Second" />
      </>,
    )

    expect(screen.getByLabelText('First')).not.toBe(
      screen.getByLabelText('Second'),
    )
  })

  it('passes the rest through to the input', async () => {
    const user = userEvent.setup()
    render(<Field label="Plex Token" type="password" name="plex_token" />)

    const input = screen.getByLabelText('Plex Token')
    await user.type(input, 'secret')

    expect(input).toHaveAttribute('type', 'password')
    expect(input).toHaveAttribute('name', 'plex_token')
    expect(input).toHaveValue('secret')
  })

  describe('when it is optional', () => {
    it('says so in the label', () => {
      render(<Field label="API Key" optional />)

      expect(screen.getByLabelText(/API Key \(optional\)/)).toBeVisible()
    })
  })

  describe('when it has a hint', () => {
    it('describes the input with it', () => {
      render(<Field label="Context Window" hint="~556 tracks" />)

      expect(
        screen.getByLabelText('Context Window'),
      ).toHaveAccessibleDescription('~556 tracks')
    })
  })

  describe('when it has an error', () => {
    it('describes the input with it', () => {
      render(<Field label="API Base URL" error="Must start with http" />)

      expect(screen.getByLabelText('API Base URL')).toHaveAccessibleDescription(
        'Must start with http',
      )
    })

    it('marks the input invalid', () => {
      render(<Field label="API Base URL" error="Must start with http" />)

      expect(screen.getByLabelText('API Base URL')).toBeInvalid()
    })

    it('announces it, for an error that arrives after the page', () => {
      render(<Field label="API Base URL" error="Bad" />)

      expect(screen.getByRole('alert')).toHaveTextContent('Bad')
    })

    it('replaces the hint, so one message is announced', () => {
      render(
        <Field
          label="API Base URL"
          hint="Where the server listens"
          error="Bad"
        />,
      )

      expect(screen.getByLabelText('API Base URL')).toHaveAccessibleDescription(
        'Bad',
      )
    })
  })

  describe('when it has neither', () => {
    it('describes the input with nothing', () => {
      render(<Field label="Plex Server URL" />)

      expect(screen.getByLabelText('Plex Server URL')).not.toHaveAttribute(
        'aria-describedby',
      )
    })

    it('leaves the input valid', () => {
      render(<Field label="Plex Server URL" />)

      expect(screen.getByLabelText('Plex Server URL')).toBeValid()
    })
  })
})
