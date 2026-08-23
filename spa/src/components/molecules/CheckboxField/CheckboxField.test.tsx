import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { CheckboxField } from './CheckboxField.tsx'

/** The form data a submit would carry, in entry order. */
function submitted(): [string, string][] {
  const form = screen.getByRole('form', { name: 'Settings' })
  return [...new FormData(form as HTMLFormElement).entries()].flatMap(
    ([name, value]): [string, string][] =>
      typeof value === 'string' ? [[name, value]] : [],
  )
}

describe('CheckboxField', () => {
  it('labels the control', () => {
    render(<CheckboxField label="Smart generation" name="smart_generation" />)

    expect(
      screen.getByRole('checkbox', { name: 'Smart generation' }),
    ).toBeVisible()
  })

  it('describes it with the hint', () => {
    render(
      <CheckboxField
        label="Smart generation"
        name="smart_generation"
        hint="Costs more."
      />,
    )

    expect(
      screen.getByRole('checkbox', { name: 'Smart generation' }),
    ).toHaveAccessibleDescription('Costs more.')
  })

  describe('what it submits', () => {
    it('carries false when it is off, which an alone checkbox cannot', () => {
      // An unchecked box is absent from FormData, and absent reads as unchanged.
      render(
        <form aria-label="Settings">
          <CheckboxField
            label="Smart generation"
            name="smart_generation"
            checked={false}
            onChange={() => undefined}
          />
        </form>,
      )

      expect(submitted()).toEqual([['smart_generation', 'false']])
    })

    it('carries true last when it is on, so the later entry wins', async () => {
      const user = userEvent.setup()
      render(
        <form aria-label="Settings">
          <CheckboxField label="Smart generation" name="smart_generation" />
        </form>,
      )

      await user.click(screen.getByRole('checkbox'))

      expect(submitted()).toEqual([
        ['smart_generation', 'false'],
        ['smart_generation', 'true'],
      ])
    })
  })
})
