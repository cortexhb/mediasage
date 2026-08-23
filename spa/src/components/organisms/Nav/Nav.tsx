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

import { Button } from '../../atoms/Button/Button.tsx'
import { MenuLink } from '../../atoms/MenuLink/MenuLink.tsx'
import { SettingsIcon } from '../../atoms/SettingsIcon/SettingsIcon.tsx'
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
        <Button
          variant="nav"
          ref={trigger}
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
        </Button>
        {open && (
          <div className={styles.nav__menu}>
            <MenuLink to={`${PLAYLIST}/prompt`} onChoose={close}>
              From Prompt
            </MenuLink>
            <MenuLink to={`${PLAYLIST}/seed`} onChoose={close}>
              From Seed Song
            </MenuLink>
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
