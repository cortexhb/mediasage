import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { CloudSettings } from './CloudSettings.tsx'
import type { CloudSettingsProps } from './CloudSettings.tsx'

/** A configured Anthropic provider. */
const PROPS: CloudSettingsProps = {
  analysis: 'claude-opus-4',
  generation: 'claude-haiku-4-5',
  smart: false,
  contextWindow: 200000,
  keySet: true,
  stored: '•••• (configured)',
}

describe('CloudSettings', () => {
  it('shows both saved model names, which only YAML could set before', () => {
    render(<CloudSettings {...PROPS} />)

    expect(screen.getByRole('textbox', { name: 'Analysis Model' })).toHaveValue(
      'claude-opus-4',
    )
    expect(
      screen.getByRole('textbox', { name: 'Generation Model' }),
    ).toHaveValue('claude-haiku-4-5')
  })

  it('starts the key field empty, so a save does not resend the stored one', () => {
    render(<CloudSettings {...PROPS} />)

    const key = screen.getByLabelText('API Key')
    expect(key).toHaveValue('')
    expect(key).toHaveAttribute('placeholder', '•••• (configured)')
  })

  it('shows the saved context window', () => {
    render(<CloudSettings {...PROPS} />)

    expect(
      screen.getByRole('spinbutton', { name: 'Context Window' }),
    ).toHaveValue(200000)
  })

  describe('the context window constraints', () => {
    it('bounds the field, since an inline error alone still submits', () => {
      render(<CloudSettings {...PROPS} />)

      const field = screen.getByRole('spinbutton', { name: 'Context Window' })
      expect(field).toHaveAttribute('min', '512')
      expect(field).toHaveAttribute('max', '2000000')
      expect(field).toBeRequired()
    })

    it.each([
      ['20000000', /Cannot exceed/],
      ['12', /Must be at least/],
    ])('reports %s inline as well', async (typed, said) => {
      const user = userEvent.setup()
      render(<CloudSettings {...PROPS} />)

      const field = screen.getByRole('spinbutton', { name: 'Context Window' })
      await user.clear(field)
      await user.type(field, typed)

      expect(await screen.findByRole('alert')).toHaveTextContent(said)
    })
  })

  describe('when the analysis model generates too', () => {
    it('says the generation model is ignored', () => {
      render(<CloudSettings {...PROPS} smart />)

      expect(
        screen.getByRole('textbox', { name: 'Generation Model' }),
      ).toHaveAccessibleDescription(/Ignored/)
    })

    it('keeps that field submittable, since read-only is not disabled', () => {
      // A disabled field is absent from FormData, which reads as unchanged.
      render(<CloudSettings {...PROPS} smart />)

      const field = screen.getByRole('textbox', { name: 'Generation Model' })
      expect(field).toHaveAttribute('readonly')
      expect(field).toBeEnabled()
    })

    it('follows the checkbox without a save', async () => {
      const user = userEvent.setup()
      render(<CloudSettings {...PROPS} />)

      await user.click(
        screen.getByRole('checkbox', {
          name: 'Use the analysis model for generation',
        }),
      )

      expect(
        screen.getByRole('textbox', { name: 'Generation Model' }),
      ).toHaveAccessibleDescription(/Ignored/)
    })
  })
})
