import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Status } from './Status.tsx'

describe('Status', () => {
  it('reports what it was given', () => {
    render(<Status state="connected">Connected</Status>)

    expect(screen.getByRole('status')).toHaveTextContent('Connected')
  })

  it.each(['connected', 'error', 'unknown'] as const)(
    'carries %s as an attribute, which is what colours it',
    (state) => {
      render(<Status state={state}>Whatever</Status>)

      expect(screen.getByRole('status')).toHaveAttribute('data-state', state)
    },
  )
})
