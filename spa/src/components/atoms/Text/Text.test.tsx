import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Text } from './Text.tsx'

describe('Text', () => {
  it('shows what it was given', () => {
    render(<Text>Reaching the API…</Text>)

    expect(screen.getByText('Reaching the API…')).toBeVisible()
  })

  it('carries its tone as an attribute, which is what colours it', () => {
    render(<Text tone="error">Nope</Text>)

    expect(screen.getByText('Nope')).toHaveAttribute('data-tone', 'error')
  })

  it('carries no tone when it is body copy', () => {
    render(<Text>Plain</Text>)

    expect(screen.getByText('Plain')).not.toHaveAttribute('data-tone')
  })

  it('announces itself when given a live role', () => {
    render(<Text role="alert">Save failed</Text>)

    expect(screen.getByRole('alert')).toHaveTextContent('Save failed')
  })

  it('takes an id, for an input that points at it', () => {
    render(<Text id="hint">~556 tracks</Text>)

    expect(screen.getByText('~556 tracks')).toHaveAttribute('id', 'hint')
  })
})
