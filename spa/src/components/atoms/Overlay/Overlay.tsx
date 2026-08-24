import { useEffect, useRef, type ReactNode } from 'react'

import styles from './Overlay.module.scss'

/**
 * A modal built on native `<dialog>`.
 *
 * `showModal()` supplies focus trapping, Escape, top-layer stacking, a
 * backdrop, and inertness of the rest of the page. That is why the six
 * near-duplicate overlays in `frontend/style.css` collapse to this one, and
 * why `focusManager` (`frontend/app.js:9`) and the scroll-lock trio
 * (`frontend/app.js:3331`) are not ported.
 *
 * `open` is the caller's state, not the element's. Escape and a
 * `form method="dialog"` submit close the element on their own, so `onClose`
 * is how the caller learns it has to catch up.
 *
 * The close button is not optional on a dialog that can be dismissed at all:
 * Escape dismisses those, and a way out only a keyboard can find is not one.
 *
 * `sticky` is the other kind, and there is exactly one -- a wait the reader
 * must not walk away from while it spends money (`molecules/WorkingOverlay`).
 * It has no close button and refuses `cancel`, which is what the legacy
 * generation overlay did by never wiring one up (`frontend/app.js:2079`).
 */
interface Shared {
  readonly open: boolean
  /** Names the dialog for assistive technology. */
  readonly label: string
  /** `compact` is the 400px card the two save dialogs use. */
  readonly size?: 'compact' | undefined
  readonly children: ReactNode
}

/** Split so the compiler rejects a sticky dialog that offers a way out. */
export type OverlayProps = Shared &
  (
    | {
        readonly sticky: true
        readonly onClose?: never
      }
    | {
        readonly sticky?: false | undefined
        /** Fired whenever the dialog closes, including by Escape. */
        readonly onClose: () => void
      }
  )

export function Overlay({
  open,
  onClose,
  label,
  size,
  sticky,
  children,
}: OverlayProps) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    // Guarded both ways: `showModal` on an open dialog is an InvalidStateError.
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      // Escape asks through `cancel`; refusing it is what keeps a sticky open.
      onCancel={
        sticky
          ? (event) => {
              event.preventDefault()
            }
          : undefined
      }
      aria-label={label}
      className={styles.overlay}
      data-size={size}
    >
      {/* Unmounted while closed: a closed dialog is hidden by the UA sheet,
          which jsdom does not apply, so its content stayed queryable. */}
      {open && (
        <>
          {!sticky && (
            <button
              type="button"
              className={styles.overlay__dismiss}
              aria-label="Close"
              // `close()` rather than `onClose`: it fires `close` for both.
              onClick={() => ref.current?.close()}
            >
              ×
            </button>
          )}
          {children}
        </>
      )}
    </dialog>
  )
}
