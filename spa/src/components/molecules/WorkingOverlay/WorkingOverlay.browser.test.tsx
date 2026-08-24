import { render, screen } from '@testing-library/react'
import { userEvent } from 'vitest/browser'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { WorkingOverlay } from './WorkingOverlay.tsx'

/**
 * Real Chromium, for the reason `atoms/Overlay`'s own test gives: jsdom
 * implements none of `showModal`, and refusing Escape is the whole point here.
 */

const STAGES = ['Reading...', 'Thinking...', 'Answering...']

/**
 * A page that starts a wait from a click.
 *
 * The click matters: Chromium only honours `preventDefault` on a dialog's
 * `cancel` once the page has user activation.
 */
function Waiting() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpen(true)
        }}
      >
        Start
      </button>
      <WorkingOverlay open={open} label="Working" steps={STAGES} />
    </>
  )
}

describe('WorkingOverlay', () => {
  it('stays shut until there is a wait', () => {
    render(<WorkingOverlay open={false} label="Working" steps={STAGES} />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('names the wait and lists its stages', () => {
    render(<WorkingOverlay open label="Working" steps={STAGES} />)

    expect(screen.getByRole('dialog', { name: 'Working' })).toBeVisible()
    for (const stage of STAGES) expect(screen.getByText(stage)).toBeVisible()
  })

  it('draws the label as a heading only when titled', () => {
    const { rerender } = render(
      <WorkingOverlay open label="Working" steps={STAGES} />,
    )
    expect(screen.queryByRole('heading', { name: 'Working' })).toBeNull()

    rerender(<WorkingOverlay open titled label="Working" steps={STAGES} />)

    expect(screen.getByRole('heading', { name: 'Working' })).toBeVisible()
  })

  it('marks the stage a stream reports', () => {
    render(<WorkingOverlay open label="Working" steps={STAGES} at={1} />)

    expect(screen.getByText(STAGES[1] ?? '')).toHaveAttribute(
      'data-state',
      'active',
    )
  })

  it('offers no way out, because leaving would not stop the work', () => {
    render(<WorkingOverlay open label="Working" steps={STAGES} />)

    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull()
  })

  it('survives Escape', async () => {
    render(<Waiting />)
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))

    await userEvent.keyboard('{Escape}')
    await userEvent.keyboard('{Escape}')

    expect(screen.getByRole('dialog', { name: 'Working' })).toBeVisible()
  })

  it('goes only when the wait does', () => {
    const { rerender } = render(
      <WorkingOverlay open label="Working" steps={STAGES} />,
    )

    rerender(<WorkingOverlay open={false} label="Working" steps={STAGES} />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
