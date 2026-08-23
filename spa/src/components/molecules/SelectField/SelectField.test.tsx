import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { SelectField } from './SelectField.tsx'

const PROVIDERS = [
  { value: 'anthropic', label: 'Anthropic (Claude)' },
  { value: 'ollama', label: 'Ollama (Local)' },
]

describe('SelectField', () => {
  it('labels its control', () => {
    render(<SelectField label="Provider" options={PROVIDERS} />)

    expect(screen.getByLabelText('Provider')).toBeVisible()
  })

  it('gives each field its own label association', () => {
    render(
      <>
        <SelectField label="Analysis Model" options={PROVIDERS} />
        <SelectField label="Generation Model" options={PROVIDERS} />
      </>,
    )

    expect(screen.getByLabelText('Analysis Model')).not.toBe(
      screen.getByLabelText('Generation Model'),
    )
  })

  it('takes a choice', async () => {
    const user = userEvent.setup()
    render(
      <SelectField label="Provider" options={PROVIDERS} name="llm_provider" />,
    )

    await user.selectOptions(screen.getByLabelText('Provider'), 'ollama')

    expect(screen.getByLabelText('Provider')).toHaveValue('ollama')
  })

  describe('when it has a hint', () => {
    it('describes the control with it', () => {
      render(
        <SelectField
          label="Provider"
          options={PROVIDERS}
          hint="Set by LLM_PROVIDER"
        />,
      )

      expect(screen.getByLabelText('Provider')).toHaveAccessibleDescription(
        'Set by LLM_PROVIDER',
      )
    })
  })

  describe('when it has none', () => {
    it('describes the control with nothing', () => {
      render(<SelectField label="Provider" options={PROVIDERS} />)

      expect(screen.getByLabelText('Provider')).not.toHaveAttribute(
        'aria-describedby',
      )
    })
  })
})
