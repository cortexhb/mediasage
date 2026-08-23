import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Chip } from './Chip.tsx'

describe('Chip', () => {
  it('carries its label and its count', () => {
    render(
      <Chip selected={false} count={7} onChoose={vi.fn()}>
        Playlists
      </Chip>,
    )

    expect(screen.getByRole('button')).toHaveTextContent('Playlists 7')
  })

  it('announces which one is in force', () => {
    // `aria-pressed`, not a class: a class says nothing to a screen reader.
    render(
      <Chip selected count={1} onChoose={vi.fn()}>
        All
      </Chip>,
    )

    expect(screen.getByRole('button', { name: /All/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('reports an unselected chip as unpressed rather than silent', () => {
    render(
      <Chip selected={false} count={1} onChoose={vi.fn()}>
        All
      </Chip>,
    )

    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'false')
  })

  it('tells the caller it was chosen', async () => {
    const chosen = vi.fn()
    render(
      <Chip selected={false} count={0} onChoose={chosen}>
        Albums
      </Chip>,
    )

    await userEvent.click(screen.getByRole('button'))

    expect(chosen).toHaveBeenCalledOnce()
  })

  it('does not submit a form it happens to sit in', () => {
    render(
      <Chip selected={false} count={0} onChoose={vi.fn()}>
        Albums
      </Chip>,
    )

    expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
  })
})
