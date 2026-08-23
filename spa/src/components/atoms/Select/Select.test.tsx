import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Select } from './Select.tsx'

const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'ollama', label: 'Ollama (Local)' },
]

describe('Select', () => {
  it('offers every option it was given', () => {
    render(<Select options={PROVIDERS} aria-label="Provider" />)

    expect(
      screen.getByRole('option', { name: 'Anthropic (Claude)' }),
    ).toBeVisible()
    expect(screen.getByRole('option', { name: 'Ollama (Local)' })).toBeVisible()
  })

  it('takes a choice', async () => {
    const user = userEvent.setup()
    render(<Select options={PROVIDERS} aria-label="Provider" />)

    await user.selectOptions(screen.getByRole('combobox'), 'ollama')

    expect(screen.getByRole('combobox')).toHaveValue('ollama')
  })

  it('starts on the value it was given', () => {
    render(
      <Select
        options={PROVIDERS}
        defaultValue="ollama"
        aria-label="Provider"
      />,
    )

    expect(screen.getByRole('combobox')).toHaveValue('ollama')
  })

  it('takes an empty option list', () => {
    // A local server with nothing pulled answers an empty model list.
    render(<Select options={[]} aria-label="Analysis Model" />)

    expect(screen.queryAllByRole('option')).toHaveLength(0)
  })

  it('disables itself when told to', () => {
    render(<Select options={[]} disabled aria-label="Analysis Model" />)

    expect(screen.getByRole('combobox')).toBeDisabled()
  })

  describe('when it has a placeholder', () => {
    it('offers it first, with an empty value', () => {
      render(
        <Select
          options={PROVIDERS}
          placeholder="-- Select model --"
          aria-label="Analysis Model"
        />,
      )

      expect(screen.getByRole('combobox')).toHaveValue('')
      expect(
        screen.getByRole('option', { name: '-- Select model --' }),
      ).toBeVisible()
    })
  })
})
