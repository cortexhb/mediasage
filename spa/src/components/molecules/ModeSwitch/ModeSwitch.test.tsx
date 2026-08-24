import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ModeSwitch } from './ModeSwitch.tsx'

describe('ModeSwitch', () => {
  it('offers both modes, with the current one pressed', () => {
    render(<ModeSwitch value="library" onChoose={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'From My Library' }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('button', { name: 'Something New' }),
    ).toHaveAttribute('aria-pressed', 'false')
  })

  it('names the mode that was clicked', async () => {
    const choose = vi.fn()
    render(<ModeSwitch value="library" onChoose={choose} />)

    await userEvent.click(screen.getByRole('button', { name: 'Something New' }))

    expect(choose).toHaveBeenCalledWith('discovery')
  })
})
