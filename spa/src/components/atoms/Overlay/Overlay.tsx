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
 */
export interface OverlayProps {
  readonly open: boolean
  /** Fired whenever the dialog closes, including by Escape. */
  readonly onClose: () => void
  /** Names the dialog for assistive technology. */
  readonly label: string
  readonly children: ReactNode
}

export function Overlay({ open, onClose, label, children }: OverlayProps) {
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
      aria-label={label}
      className={styles.overlay}
    >
      {children}
    </dialog>
  )
}
