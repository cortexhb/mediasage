/**
 * Every route in the app, in one place.
 *
 * Data mode: routes are plain objects, not JSX, so this file holds no markup
 * and needs no `.tsx`. Loaders fetch a page's data before it renders, which is
 * why a page never fetches from inside an effect.
 *
 * A route is declared when its page is built, not ahead of it. The
 * navigation already links to `/playlist` and `/recommend`; each answers
 * `NotFound` until its phase lands.
 */
import type { RouteObject } from 'react-router'

import { Shell } from './components/organisms/Shell/Shell.tsx'
import { loadHistory } from './libs/loadHistory/loadHistory.ts'
import { loadSettings } from './libs/loadSettings/loadSettings.ts'
import { loadStats } from './libs/loadStats/loadStats.ts'
import { probeOllama } from './libs/probeOllama/probeOllama.ts'
import { ErrorPage } from './pages/ErrorPage/ErrorPage.tsx'
import { Home } from './pages/Home/Home.tsx'
import { NotFound } from './pages/NotFound/NotFound.tsx'
import { Settings } from './pages/Settings/Settings.tsx'

export const routes: RouteObject[] = [
  {
    // Pathless: the shell wraps every route without owning a segment.
    Component: Shell,
    children: [
      {
        // Below the shell, so a failed page keeps the header.
        ErrorBoundary: ErrorPage,
        children: [
          { index: true, Component: Home, loader: loadHistory },
          {
            // No action: the save is a plain call, see `libs/saveSettings`.
            path: 'settings',
            Component: Settings,
            loader: loadSettings,
          },
          {
            // No component: the settings form loads this through a fetcher,
            // to probe an Ollama endpoint it has not saved yet.
            path: 'settings/ollama',
            loader: probeOllama,
          },
          {
            // No component: the Plex card fetches its counts from here.
            path: 'settings/stats',
            loader: loadStats,
          },
          { path: '*', Component: NotFound },
        ],
      },
    ],
  },
]
