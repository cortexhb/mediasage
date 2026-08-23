/**
 * Every route in the app, in one place.
 *
 * Data mode: routes are plain objects, not JSX, so this file holds no markup
 * and needs no `.tsx`. Loaders fetch a page's data before it renders, which is
 * why a page never fetches from inside an effect.
 *
 * Routes are declared when their page is built, not ahead of it. The
 * navigation already links to `/playlist`, `/recommend` and `/settings`; each
 * answers `NotFound` until its phase lands.
 */
import type { RouteObject } from 'react-router'

import { Shell } from './components/organisms/Shell/Shell.tsx'
import { NotFound } from './pages/NotFound/NotFound.tsx'
import App from './App.tsx'

export const routes: RouteObject[] = [
  {
    // Pathless: the shell wraps every route without owning a segment.
    Component: Shell,
    children: [
      { index: true, Component: App },
      { path: '*', Component: NotFound },
    ],
  },
]
