/**
 * The list of settings groups, down the left of the page.
 *
 * `NavLink` rather than buttons: each group is a route, so the browser's back
 * button walks them and a link to one can be shared. `aria-current="page"` is
 * what `NavLink` sets, and it is what marks the group in force.
 */
import { NavLink } from 'react-router'

import { SETTINGS_GROUPS } from '../../../libs/settingsGroups/settingsGroups.ts'
import styles from './SettingsRail.module.scss'

export function SettingsRail() {
  return (
    <nav className={styles.settingsRail} aria-label="Settings groups">
      <ul className={styles.settingsRail__list}>
        {SETTINGS_GROUPS.map((group) => (
          <li key={group.slug}>
            <NavLink
              to={group.slug}
              className={({ isActive }) =>
                [
                  styles.settingsRail__link,
                  isActive ? styles['settingsRail__link--active'] : '',
                ].join(' ')
              }
            >
              {group.title}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
