/**
 * A link inside a dropdown, checked while its route is the open one.
 *
 * The checkmark is the legacy `.nav-check` behaviour from
 * `frontend/app.js:991`: rendered even when empty, so labels stay aligned.
 */
import { NavLink } from 'react-router'

import styles from './MenuLink.module.scss'

export interface MenuLinkProps {
  readonly to: string
  /** Called when the entry is chosen, for a menu that closes itself. */
  readonly onChoose?: () => void
  readonly children: string
}

export function MenuLink({ to, onChoose, children }: MenuLinkProps) {
  return (
    <NavLink
      to={to}
      onClick={onChoose}
      // The string form rejects a lookup's `undefined`; the function form takes it.
      className={() => styles.menuLink}
    >
      {({ isActive }) => (
        <>
          <span className={styles.menuLink__check} aria-hidden="true">
            {isActive ? '✓' : ''}
          </span>
          {children}
        </>
      )}
    </NavLink>
  )
}
