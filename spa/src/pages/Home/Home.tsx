/**
 * The landing page: what the app can make, and what it has made.
 *
 * `frontend/index.html:40` opened this screen with a setup wizard. There is no
 * wizard here — Settings is the only configuration surface, per
 * `spa/docs/migration.md` — so the greeting is the first thing rendered.
 */
import { useLoaderData } from 'react-router'

import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { HistoryFeed } from '../../components/organisms/HistoryFeed/HistoryFeed.tsx'
import { ModeCard } from '../../components/molecules/ModeCard/ModeCard.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import type { HistoryPage } from '../../libs/loadHistory/loadHistory.ts'
import { useSharedLibrarySync } from '../../libs/useLibrarySync/useLibrarySync.ts'
import styles from './Home.module.scss'

/** Why the three cards are shut while the cache is being rewritten. */
const SYNCING =
  'Library data is syncing… Playlist Generation and Album Recommendations will be disabled until it finishes'

/** The three things the app makes, and where each one starts. */
const MODES = [
  {
    to: '/playlist/prompt',
    mode: 'prompt_playlist',
    title: 'Playlist from Prompt',
    description: 'Describe a vibe and let AI curate tracks',
  },
  {
    to: '/playlist/seed',
    mode: 'seed_playlist',
    title: 'Playlist from Seed',
    description: 'Start from a song you love',
  },
  {
    to: '/recommend',
    mode: 'album_recommendation',
    title: 'Recommend Album',
    description: 'Find the perfect album for the moment',
  },
] as const

export function Home() {
  const page = useLoaderData<HistoryPage>()
  const sync = useSharedLibrarySync()
  const syncing = sync.status?.is_syncing ?? false

  return (
    <div className={styles.home}>
      <div className={styles.home__intro}>
        <Heading level={2}>What do you want to listen to?</Heading>
        <Text tone="secondary">
          {syncing
            ? SYNCING
            : 'Create playlists and discover albums from your library.'}
        </Text>
      </div>

      <div className={styles.home__modes}>
        {MODES.map((entry) => (
          <ModeCard key={entry.to} {...entry} disabled={syncing} />
        ))}
      </div>

      <section className={styles.home__history}>
        <Heading level={3}>Recent activity</Heading>
        <HistoryFeed page={page} />
      </section>
    </div>
  )
}
