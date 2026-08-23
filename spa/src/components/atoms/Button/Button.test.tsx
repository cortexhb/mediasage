import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Button } from './Button.tsx'

describe('Button', () => {
  it('reports being pressed', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Button variant="primary" onClick={onClick}>
        Save Settings
      </Button>,
    )

    await user.click(screen.getByRole('button', { name: 'Save Settings' }))

    expect(onClick).toHaveBeenCalledOnce()
  })

  it('carries its variant as an attribute, which is what styles it', () => {
    render(<Button variant="ghost">Back</Button>)

    expect(screen.getByRole('button')).toHaveAttribute('data-variant', 'ghost')
  })

  it('does not submit the form it sits in unless asked', () => {
    // The HTML default is submit, which is the mistake this guards.
    render(<Button variant="primary">Refresh</Button>)

    expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
  })

  it('submits when it is the form control', () => {
    render(
      <Button variant="primary" type="submit">
        Save Settings
      </Button>,
    )

    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit')
  })

  it('refuses to be pressed while disabled', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Button variant="primary" disabled onClick={onClick}>
        Saving…
      </Button>,
    )

    await user.click(screen.getByRole('button'))

    expect(onClick).not.toHaveBeenCalled()
  })
})
