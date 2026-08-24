/**
 * Every route in the app, in one place.
 *
 * Data mode: routes are plain objects, not JSX, so this file holds no markup
 * and needs no `.tsx`. Loaders fetch a page's data before it renders, which is
 * why a page never fetches from inside an effect.
 *
 * A route is declared when its page is built, not ahead of it, so a link in
 * the navigation can answer `NotFound` until its phase lands.
 */
import type { RouteObject } from 'react-router'

import { Shell } from './components/organisms/Shell/Shell.tsx'
import { actOnRecommendation } from './libs/actOnRecommendation/actOnRecommendation.ts'
import { answerAlbumQuestions } from './libs/answerAlbumQuestions/answerAlbumQuestions.ts'
import { askAlbumQuestions } from './libs/askAlbumQuestions/askAlbumQuestions.ts'
import { askPromptQuestions } from './libs/askPromptQuestions/askPromptQuestions.ts'
import { chooseAlbumFilters } from './libs/chooseAlbumFilters/chooseAlbumFilters.ts'
import { chooseDimensions } from './libs/chooseDimensions/chooseDimensions.ts'
import { chooseFilters } from './libs/chooseFilters/chooseFilters.ts'
import { loadAlbumFilters } from './libs/loadAlbumFilters/loadAlbumFilters.ts'
import { loadAlbumRefine } from './libs/loadAlbumRefine/loadAlbumRefine.ts'
import { loadAlbumResults } from './libs/loadAlbumResults/loadAlbumResults.ts'
import { loadDimensions } from './libs/loadDimensions/loadDimensions.ts'
import { loadFilters } from './libs/loadFilters/loadFilters.ts'
import { loadFooter } from './libs/loadFooter/loadFooter.ts'
import { loadHistory } from './libs/loadHistory/loadHistory.ts'
import { loadRefine } from './libs/loadRefine/loadRefine.ts'
import { loadSeedSearch } from './libs/loadSeedSearch/loadSeedSearch.ts'
import { pickSeedTrack } from './libs/pickSeedTrack/pickSeedTrack.ts'
import { loadSettings } from './libs/loadSettings/loadSettings.ts'
import { loadStats } from './libs/loadStats/loadStats.ts'
import { loadPlaylist } from './libs/loadPlaylist/loadPlaylist.ts'
import {
  ALBUM_PREVIEW,
  previewAlbums,
} from './libs/previewAlbums/previewAlbums.ts'
import {
  PREVIEW,
  previewSelection,
} from './libs/previewSelection/previewSelection.ts'
import { probeOllama } from './libs/probeOllama/probeOllama.ts'
import { refinePrompt } from './libs/refinePrompt/refinePrompt.ts'
import { savePlaylistToPlex } from './libs/savePlaylistToPlex/savePlaylistToPlex.ts'
import { AlbumFilters } from './pages/AlbumFilters/AlbumFilters.tsx'
import { AlbumPrompt } from './pages/AlbumPrompt/AlbumPrompt.tsx'
import { AlbumRefine } from './pages/AlbumRefine/AlbumRefine.tsx'
import { AlbumResults } from './pages/AlbumResults/AlbumResults.tsx'
import { DimensionsStep } from './pages/DimensionsStep/DimensionsStep.tsx'
import { ErrorPage } from './pages/ErrorPage/ErrorPage.tsx'
import { FiltersStep } from './pages/FiltersStep/FiltersStep.tsx'
import { Home } from './pages/Home/Home.tsx'
import { NotFound } from './pages/NotFound/NotFound.tsx'
import { PlaylistStep } from './pages/PlaylistStep/PlaylistStep.tsx'
import { PromptStep } from './pages/PromptStep/PromptStep.tsx'
import { RefineStep } from './pages/RefineStep/RefineStep.tsx'
import { SeedStep } from './pages/SeedStep/SeedStep.tsx'
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
            path: 'playlist/seed',
            Component: SeedStep,
            loader: loadSeedSearch,
            action: pickSeedTrack,
          },
          {
            path: 'playlist/seed/dimensions',
            Component: DimensionsStep,
            loader: loadDimensions,
            action: chooseDimensions,
          },
          {
            // Shared: both flows narrow the same library the same way, and
            // the loader answers from whichever record is in play.
            path: 'playlist/:mode/filters',
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
            path: 'playlist/:mode/playlist',
            Component: PlaylistStep,
            loader: loadPlaylist,
            action: savePlaylistToPlex,
          },
          {
            // No loader: the prompt is typed, not read.
            path: 'recommend',
            Component: AlbumPrompt,
            action: askAlbumQuestions,
          },
          {
            path: 'recommend/refine',
            Component: AlbumRefine,
            loader: loadAlbumRefine,
            action: answerAlbumQuestions,
          },
          {
            path: 'recommend/filters',
            Component: AlbumFilters,
            loader: loadAlbumFilters,
            action: chooseAlbumFilters,
          },
          {
            path: 'recommend/results',
            Component: AlbumResults,
            loader: loadAlbumResults,
            action: actOnRecommendation,
          },
          {
            // No component: the album filters step counts its selection here.
            path: ALBUM_PREVIEW.slice(1),
            loader: previewAlbums,
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
