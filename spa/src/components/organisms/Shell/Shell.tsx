/**
 * The layout every page renders inside: header, navigation, main.
 *
 * It is the parent of every route, so the header is mounted once and survives
 * navigation. `#main-content` is the target of the skip link in
 * `index.html`, which sits outside `#root` and must always find it here.
 */
import { Link, Outlet } from 'react-router'

import { Nav } from '../Nav/Nav.tsx'
import styles from './Shell.module.scss'

export function Shell() {
  return (
    <div className={styles.shell}>
      <header className={styles.shell__header}>
        <h1 className={styles.shell__logo}>
          <Link to="/" className={styles.shell__logoLink}>
            MediaSage
          </Link>
        </h1>
        <Nav />
      </header>
      <main id="main-content">
        <Outlet />
      </main>
    </div>
  )
}
