import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { CustomSettings } from './CustomSettings.tsx'

/** An MLX server, keyless, with a window it had to be told about. */
const PROPS = {
  endpoint: 'http://localhost:5000/v1',
  model: 'qwen3-30b',
  contextWindow: 32768,
  keySet: false,
  stored: '•••• (configured)',
}

describe('CustomSettings', () => {
  it('shows the saved endpoint and model', () => {
    render(<CustomSettings {...PROPS} />)

    expect(screen.getByRole('textbox', { name: 'API Base URL' })).toHaveValue(
      'http://localhost:5000/v1',
    )
    expect(screen.getByRole('textbox', { name: 'Model Name' })).toHaveValue(
      'qwen3-30b',
    )
  })

  it('requires an endpoint, since there is no default to fall back to', () => {
    render(<CustomSettings {...PROPS} endpoint={undefined} />)

    const url = screen.getByRole('textbox', { name: 'API Base URL' })
    expect(url).toBeRequired()
    expect(url).toHaveValue('')
  })

  describe('the API key', () => {
    it('is marked optional, since a local server usually wants none', () => {
      render(<CustomSettings {...PROPS} keySet={false} />)

      expect(screen.getByLabelText(/API Key/)).toBeInTheDocument()
      expect(screen.getByText(/optional/i)).toBeVisible()
    })

    it('marks a stored key in the placeholder', () => {
      render(<CustomSettings {...PROPS} keySet />)

      expect(screen.getByLabelText(/API Key/)).toHaveAttribute(
        'placeholder',
        '•••• (configured)',
      )
    })
  })

  it('says the one model name covers generation too', () => {
    render(<CustomSettings {...PROPS} />)

    expect(
      screen.getByRole('textbox', { name: 'Model Name' }),
    ).toHaveAccessibleDescription('Used for analysis and for generation both.')
  })

  describe('the context window', () => {
    it('is typed, since nothing here reports it', () => {
      render(<CustomSettings {...PROPS} />)

      expect(
        screen.getByRole('spinbutton', { name: 'Context Window' }),
      ).toHaveValue(32768)
    })

    it('refuses a window too small to hold the instructions', () => {
      render(<CustomSettings {...PROPS} />)

      expect(
        screen.getByRole('spinbutton', { name: 'Context Window' }),
      ).toHaveAttribute('min', '512')
    })

    it('translates the saved value into tracks', () => {
      render(<CustomSettings {...PROPS} contextWindow={32768} />)

      expect(
        screen.getByRole('spinbutton', { name: 'Context Window' }),
      ).toHaveAccessibleDescription('~569 tracks fit in it')
    })

    it('retranslates as it is typed, not only once it is saved', async () => {
      const user = userEvent.setup()
      render(<CustomSettings {...PROPS} />)

      const field = screen.getByRole('spinbutton', { name: 'Context Window' })
      await user.clear(field)
      await user.type(field, '128000')

      expect(field).toHaveAccessibleDescription('~2,284 tracks fit in it')
    })

    it('says what is wrong with a window too small to use', async () => {
      const user = userEvent.setup()
      render(<CustomSettings {...PROPS} />)

      const field = screen.getByRole('spinbutton', { name: 'Context Window' })
      await user.clear(field)
      await user.type(field, '100')

      expect(field).toBeInvalid()
      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Must be at least 512 tokens',
      )
    })

    it('replaces the error with the count once the value is usable', async () => {
      const user = userEvent.setup()
      render(<CustomSettings {...PROPS} />)

      const field = screen.getByRole('spinbutton', { name: 'Context Window' })
      await user.clear(field)
      expect(screen.getByRole('alert')).toBeVisible()

      await user.type(field, '8192')

      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(field).toHaveAccessibleDescription('~127 tracks fit in it')
    })
  })

  describe('the endpoint', () => {
    it('says nothing while it is still being typed', async () => {
      const user = userEvent.setup()
      render(<CustomSettings {...PROPS} />)

      const field = screen.getByRole('textbox', { name: 'API Base URL' })
      await user.clear(field)
      await user.type(field, 'localhos')

      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('judges it once it has been left', async () => {
      const user = userEvent.setup()
      render(<CustomSettings {...PROPS} />)

      const field = screen.getByRole('textbox', { name: 'API Base URL' })
      await user.clear(field)
      await user.type(field, 'nonsense')
      await user.tab()

      expect(field).toBeInvalid()
      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Invalid URL format',
      )
    })

    it('rejects a scheme fetch cannot use', async () => {
      const user = userEvent.setup()
      render(<CustomSettings {...PROPS} />)

      const field = screen.getByRole('textbox', { name: 'API Base URL' })
      await user.clear(field)
      await user.type(field, 'ftp://box/v1')
      await user.tab()

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Must use http or https protocol',
      )
    })

    it('clears the error once the address is fixed', async () => {
      const user = userEvent.setup()
      render(<CustomSettings {...PROPS} />)

      const field = screen.getByRole('textbox', { name: 'API Base URL' })
      await user.clear(field)
      await user.type(field, 'nonsense')
      await user.tab()
      expect(screen.getByRole('alert')).toBeVisible()

      await user.clear(field)
      await user.type(field, 'http://box:5000/v1')

      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  describe('the context window constraints', () => {
    it('bounds the field, since an inline error alone still submits', () => {
      render(<CustomSettings {...PROPS} />)

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
      render(<CustomSettings {...PROPS} />)

      const field = screen.getByRole('spinbutton', { name: 'Context Window' })
      await user.clear(field)
      await user.type(field, typed)

      expect(await screen.findByRole('alert')).toHaveTextContent(said)
    })
  })
})
