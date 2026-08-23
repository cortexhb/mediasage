import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ProgressBar } from './ProgressBar.tsx'

describe('ProgressBar', () => {
  it('reports where it has got to', () => {
    render(<ProgressBar percent={42} label="Library sync progress" />)

    expect(
      screen.getByRole('progressbar', { name: 'Library sync progress' }),
    ).toHaveAttribute('aria-valuenow', '42')
  })

  it.each([
    [-5, '0'],
    [140, '100'],
  ])('clamps %i to %s', (given, expected) => {
    // A sync can process more than the total it first counted.
    render(<ProgressBar percent={given} label="Progress" />)

    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      expected,
    )
  })

  it('rounds, since a bar has no use for decimals', () => {
    render(<ProgressBar percent={33.7} label="Progress" />)

    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '34',
    )
  })

  it('states no value at all when nothing is measurable', () => {
    // An absent `aria-valuenow` is how ARIA says indeterminate; a zero would
    // announce a sync that has stalled.
    render(<ProgressBar percent={null} label="Progress" />)

    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
  })

  it('keeps its bounds so the role stays well formed', () => {
    render(<ProgressBar percent={null} label="Progress" />)

    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuemin', '0')
    expect(bar).toHaveAttribute('aria-valuemax', '100')
  })
})
