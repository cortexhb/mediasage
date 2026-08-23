/**
 * The header navigation: a playlist disclosure, Recommend Album, Settings.
 *
 * `NavLink` owns the active state the legacy code recomputed by hand in
 * `updateView` (`frontend/app.js:979-1002`), and sets `aria-current="page"`
 * itself rather than writing `aria-current="false"` on every inactive entry.
 * The stylesheet selects on that attribute, so every `className` here is a
 * static one.
 *
 * The dropdown is a disclosure, not a menu. `frontend/index.html:23` declares
 * `role="menu"` and `role="menuitem"` but `frontend/app.js` binds only Escape
 * — no arrow keys, no Home/End, no roving focus. Keeping the roles would
 * promise a keyboard contract the component does not implement.
 *
 * Entries link to routes that do not exist yet; each goes live with its
 * phase. See `spa/docs/migration.md`.
 */
import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router'

import styles from './Nav.module.scss'

/** Both create modes, and the prefix that marks the disclosure active. */
const PLAYLIST = '/playlist'

export function Nav() {
  const [open, setOpen] = useState(false)
  const dropdown = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const location = useLocation()
  const onPlaylist = location.pathname.startsWith(PLAYLIST)
  const close = () => {
    setOpen(false)
  }

  useEffect(() => {
    if (!open) return

    const dismiss = (event: MouseEvent) => {
      const target = event.target
      if (target instanceof Node && dropdown.current?.contains(target)) return
      setOpen(false)
    }

    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      // Focus would otherwise land on `body` with nothing to tab from.
      trigger.current?.focus()
    }

    document.addEventListener('click', dismiss)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('click', dismiss)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return (
    <nav className={styles.nav} aria-label="Main navigation">
      <div className={styles.nav__dropdown} ref={dropdown}>
        <button
          type="button"
          ref={trigger}
          className={styles.nav__trigger}
          aria-expanded={open}
          // Not `page`: the trigger is the section, not the page.
          aria-current={onPlaylist ? 'true' : undefined}
          onClick={() => {
            setOpen(!open)
          }}
        >
          Make Playlist{' '}
          <span className={styles.nav__chevron} aria-hidden="true">
            ▾
          </span>
        </button>
        {open && (
          <div className={styles.nav__menu}>
            <DropdownItem to={`${PLAYLIST}/prompt`} onChosen={close}>
              From Prompt
            </DropdownItem>
            <DropdownItem to={`${PLAYLIST}/seed`} onChosen={close}>
              From Seed Song
            </DropdownItem>
          </div>
        )}
      </div>

      <NavLink to="/recommend">Recommend Album</NavLink>

      <NavLink to="/settings" aria-label="Settings">
        <SettingsIcon />
      </NavLink>
    </nav>
  )
}

/**
 * One entry inside the disclosure, with the legacy checkmark for the mode in
 * use (`frontend/app.js:991`).
 *
 * It closes the disclosure itself. Watching the location instead would mean
 * setting state from an effect, and a click inside the dropdown is exempt
 * from the outside-click handler.
 */
function DropdownItem({
  to,
  onChosen,
  children,
}: {
  to: string
  onChosen: () => void
  children: string
}) {
  return (
    <NavLink to={to} onClick={onChosen}>
      {({ isActive }) => (
        <>
          <span className={styles.nav__check} aria-hidden="true">
            {isActive ? '✓' : ''}
          </span>
          {children}
        </>
      )}
    </NavLink>
  )
}

/** Copied from `frontend/index.html:33`; the only icon the header carries. */
function SettingsIcon() {
  return (
    <svg
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}
