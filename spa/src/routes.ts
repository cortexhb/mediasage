/**
 * Every route in the app, in one place.
 *
 * Data mode: routes are plain objects, not JSX, so this file holds no markup
 * and needs no `.tsx`. Loaders fetch a page's data before it renders, which is
 * why a page never fetches from inside an effect.
 */
import type { RouteObject } from 'react-router'

import App from './App.tsx'

export const routes: RouteObject[] = [
  {
    path: '/',
    Component: App,
  },
]
