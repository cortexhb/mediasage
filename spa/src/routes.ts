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
import { askPromptQuestions } from './libs/askPromptQuestions/askPromptQuestions.ts'
import { chooseFilters } from './libs/chooseFilters/chooseFilters.ts'
import { loadFilters } from './libs/loadFilters/loadFilters.ts'
import { loadFooter } from './libs/loadFooter/loadFooter.ts'
import { loadHistory } from './libs/loadHistory/loadHistory.ts'
import { loadRefine } from './libs/loadRefine/loadRefine.ts'
import { loadSettings } from './libs/loadSettings/loadSettings.ts'
import { loadStats } from './libs/loadStats/loadStats.ts'
import { loadPlaylist } from './libs/loadPlaylist/loadPlaylist.ts'
import {
  PREVIEW,
  previewSelection,
} from './libs/previewSelection/previewSelection.ts'
import { probeOllama } from './libs/probeOllama/probeOllama.ts'
import { refinePrompt } from './libs/refinePrompt/refinePrompt.ts'
import { savePlaylistToPlex } from './libs/savePlaylistToPlex/savePlaylistToPlex.ts'
import { ErrorPage } from './pages/ErrorPage/ErrorPage.tsx'
import { FiltersStep } from './pages/FiltersStep/FiltersStep.tsx'
import { Home } from './pages/Home/Home.tsx'
import { NotFound } from './pages/NotFound/NotFound.tsx'
import { PlaylistStep } from './pages/PlaylistStep/PlaylistStep.tsx'
import { PromptStep } from './pages/PromptStep/PromptStep.tsx'
import { RefineStep } from './pages/RefineStep/RefineStep.tsx'
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
            // No loader: the prompt is typed, not read.
            path: 'playlist/prompt',
            Component: PromptStep,
            action: askPromptQuestions,
          },
          {
            path: 'playlist/prompt/refine',
            Component: RefineStep,
            loader: loadRefine,
            action: refinePrompt,
          },
          {
            path: 'playlist/prompt/filters',
            Component: FiltersStep,
            loader: loadFilters,
            action: chooseFilters,
            // The preview fetcher would otherwise re-read config per click.
            shouldRevalidate: ({ formAction }) => formAction !== PREVIEW,
          },
          {
            // No component: the filters step previews its selection here.
            path: PREVIEW.slice(1),
            action: previewSelection,
          },
          {
            path: 'playlist/prompt/playlist',
            Component: PlaylistStep,
            loader: loadPlaylist,
            action: savePlaylistToPlex,
          },
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
          {
            // No component: the status bar fetches version and model here.
            path: 'footer',
            loader: loadFooter,
            // Never again: neither can change under a running page, and an
            // active fetcher is re-run by every action on every page.
            shouldRevalidate: () => false,
          },
          { path: '*', Component: NotFound },
        ],
      },
    ],
  },
]
