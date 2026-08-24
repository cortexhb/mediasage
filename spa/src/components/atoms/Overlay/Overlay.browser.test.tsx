import { render, screen } from '@testing-library/react'
import { userEvent } from 'vitest/browser'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { Overlay } from './Overlay.tsx'

/**
 * Real Chromium, not jsdom.
 *
 * jsdom 30.0.1 declares `HTMLDialogElement` but implements none of `show`,
 * `showModal` or `close`, and happy-dom's `showModal` is only
 * `setAttribute('open', '')`. Shimming either would mean these assertions
 * described the shim rather than the platform the component delegates to.
 *
 * Input comes from `vitest/browser` rather than
 * `@testing-library/user-event`, because Escape-to-close and the focus trap
 * are driven by the browser and ignore synthesised events.
 */

/** The caller's state and the element's, wired the way a page wires them. */
function Controlled({ onClose = () => undefined }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button type="button">Behind</button>
      <button
        type="button"
        onClick={() => {
          setOpen(true)
        }}
      >
        Open
      </button>
      <Overlay
        open={open}
        label="Save playlist"
        onClose={() => {
          setOpen(false)
          onClose()
        }}
      >
        <button type="button">Confirm</button>
        <button type="button">Cancel</button>
      </Overlay>
    </>
  )
}

/** The other kind: a wait the reader is not offered a way out of. */
function Sticky() {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpen(true)
        }}
      >
        Open
      </button>
      <Overlay open={open} sticky label="Generating">
        <p>Body</p>
      </Overlay>
    </>
  )
}

/** What the browser would hand a click at this element's centre. */
function topmostOver(element: Element): Element | null {
  const box = element.getBoundingClientRect()
  return document.elementFromPoint(
    box.left + box.width / 2,
    box.top + box.height / 2,
  )
}

describe('Overlay', () => {
  it('is absent from the accessibility tree while closed', () => {
    render(
      <Overlay open={false} label="Save playlist" onClose={vi.fn()}>
        <p>Body</p>
      </Overlay>,
    )

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens when the caller says so', () => {
    render(
      <Overlay open label="Save playlist" onClose={vi.fn()}>
        <p>Body</p>
      </Overlay>,
    )

    expect(screen.getByRole('dialog', { name: 'Save playlist' })).toBeVisible()
    expect(screen.getByText('Body')).toBeVisible()
  })

  it('renders whatever it is given', () => {
    render(
      <Overlay open label="Save playlist" onClose={vi.fn()}>
        <button type="button">Confirm</button>
      </Overlay>,
    )

    expect(screen.getByRole('button', { name: 'Confirm' })).toBeVisible()
  })

  it('does not reopen a dialog that is already open', () => {
    const { rerender } = render(
      <Overlay open label="Save playlist" onClose={vi.fn()}>
        <p>Body</p>
      </Overlay>,
    )

    // A second showModal on an open dialog throws InvalidStateError.
    rerender(
      <Overlay open label="Save playlist" onClose={vi.fn()}>
        <p>Body again</p>
      </Overlay>,
    )

    expect(screen.getByText('Body again')).toBeVisible()
  })

  describe('what the platform supplies', () => {
    it('moves focus into the dialog, onto the way out of it', async () => {
      render(<Controlled />)

      await userEvent.click(screen.getByRole('button', { name: 'Open' }))

      expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus()
    })

    it('covers the page behind it, so a click cannot reach it', async () => {
      render(<Controlled />)
      const behind = screen.getByRole('button', { name: 'Behind' })

      await userEvent.click(screen.getByRole('button', { name: 'Open' }))

      // The backdrop is in the top layer, above every stacking context.
      expect(topmostOver(behind)).not.toBe(behind)
    })

    it('never lets Tab reach the page behind it', async () => {
      render(<Controlled />)
      const outside = [
        screen.getByRole('button', { name: 'Behind' }),
        screen.getByRole('button', { name: 'Open' }),
      ]

      await userEvent.click(screen.getByRole('button', { name: 'Open' }))
      // Six presses laps the two buttons inside more than once. The order
      // passes through the document between laps, so this asserts on what
      // focus never reaches, not on where it lands.
      for (let press = 0; press < 6; press += 1) {
        await userEvent.tab()
        for (const button of outside) expect(button).not.toHaveFocus()
      }
    })

    it('closes from the button, for anyone not reaching for Escape', async () => {
      const onClose = vi.fn()
      render(<Controlled onClose={onClose} />)
      await userEvent.click(screen.getByRole('button', { name: 'Open' }))

      await userEvent.click(screen.getByRole('button', { name: 'Close' }))

      expect(onClose).toHaveBeenCalledOnce()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('closes on Escape and tells the caller', async () => {
      const onClose = vi.fn()
      render(<Controlled onClose={onClose} />)

      await userEvent.click(screen.getByRole('button', { name: 'Open' }))
      await userEvent.keyboard('{Escape}')

      expect(onClose).toHaveBeenCalledOnce()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('gives the page back once it closes', async () => {
      render(<Controlled />)
      const behind = screen.getByRole('button', { name: 'Behind' })
      await userEvent.click(screen.getByRole('button', { name: 'Open' }))

      await userEvent.keyboard('{Escape}')

      expect(topmostOver(behind)).toBe(behind)
    })

    it('refuses Escape when the caller says the dialog is sticky', async () => {
      render(<Sticky />)
      // Clicked first: Chromium ignores `preventDefault` on `cancel` with no
      // user activation behind it.
      await userEvent.click(screen.getByRole('button', { name: 'Open' }))

      await userEvent.keyboard('{Escape}')

      expect(screen.getByRole('dialog', { name: 'Generating' })).toBeVisible()
    })

    it('gives a sticky dialog no close button', () => {
      render(
        <Overlay open sticky label="Generating">
          <p>Body</p>
        </Overlay>,
      )

      expect(screen.queryByRole('button', { name: 'Close' })).toBeNull()
    })

    it('paints a backdrop', async () => {
      render(<Controlled />)
      await userEvent.click(screen.getByRole('button', { name: 'Open' }))

      const dialog = screen.getByRole('dialog')

      expect(getComputedStyle(dialog, '::backdrop').backgroundColor).toBe(
        'rgba(26, 26, 26, 0.8)',
      )
    })
  })
})
