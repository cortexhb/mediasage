/**
 * The layout every page renders inside: header, navigation, main.
 *
 * It is the parent of every route, so the header is mounted once and survives
 * navigation. `#main-content` is the target of the skip link in
 * `index.html`, which sits outside `#root` and must always find it here.
 *
 * It also anchors the library-sync poller, for the same reason: one per app.
 */
import { Link, Outlet, useMatch } from 'react-router'

import { Heading } from '../../atoms/Heading/Heading.tsx'
import { Footer } from '../Footer/Footer.tsx'
import { LibrarySyncProvider } from '../LibrarySyncProvider/LibrarySyncProvider.tsx'
import { Nav } from '../Nav/Nav.tsx'
import styles from './Shell.module.scss'

export function Shell() {
  // `frontend/app.js:1058`: the results grid is the one screen that widens.
  const wide = useMatch('/playlist/:mode/playlist')

  return (
    <LibrarySyncProvider>
      <div className={styles.shell} data-wide={wide ? 'true' : undefined}>
        <header className={styles.shell__header}>
          <div className={styles.shell__logo}>
            <Heading level={1}>
              <Link to="/">MediaSage</Link>
            </Heading>
          </div>
          <Nav />
        </header>
        {/* Focusable, or the skip link only scrolls and leaves focus behind. */}
        <main id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <Footer />
      </div>
    </LibrarySyncProvider>
  )
}
