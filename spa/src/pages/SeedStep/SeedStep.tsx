/**
 * Step one of the seed flow: find a song to start from.
 *
 * Two forms, because they do different things. Searching is a GET that puts
 * the query in the URL and re-runs the loader, so a reload or a back keeps the
 * results. Picking a result is a POST: it spends an LLM call analysing the
 * track, which is why it is an action.
 *
 * Each result is a submit button carrying its own rating key, so the pick
 * needs no click handler and no state -- the activated button is what the
 * form sends.
 */
import { Form, useActionData, useLoaderData, useNavigation } from 'react-router'

import { AlbumArt } from '../../components/atoms/AlbumArt/AlbumArt.tsx'
import { Button } from '../../components/atoms/Button/Button.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { Input } from '../../components/atoms/Input/Input.tsx'
import { Text } from '../../components/atoms/Text/Text.tsx'
import { Stepper } from '../../components/molecules/Stepper/Stepper.tsx'
import { WorkingOverlay } from '../../components/molecules/WorkingOverlay/WorkingOverlay.tsx'
import type { SeedSearchData } from '../../libs/loadSeedSearch/loadSeedSearch.ts'
import type { SeedActionResult } from '../../libs/pickSeedTrack/pickSeedTrack.ts'
import { playlistSteps } from '../../libs/flowSteps/flowSteps.ts'
import styles from './SeedStep.module.scss'

/** The stages `frontend/app.js:2947` named for this same wait. */
const STAGES = [
  'Loading track metadata...',
  'Analyzing musical characteristics...',
  'Generating exploration dimensions...',
]

export function SeedStep() {
  const { query, tracks, error } = useLoaderData<SeedSearchData>()
  const failed = useActionData<SeedActionResult>()
  const navigation = useNavigation()
  const analysing = navigation.state === 'submitting'

  return (
    <div className={styles.seed}>
      <Stepper steps={playlistSteps('seed')} current={1} />

      <Heading level={2}>Find a song you like</Heading>
      <p className={styles.seed__description}>
        Search for a track to use as the starting point.
      </p>

      <Form method="get" role="search" className={styles.seed__search}>
        <Input
          name="q"
          type="text"
          defaultValue={query}
          placeholder="Search by title or artist..."
          aria-label="Search for tracks"
        />
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </Form>

      {(error ?? failed) && (
        <Text tone="error" role="alert">
          {error ?? failed?.error}
        </Text>
      )}

      <Form method="post">
        <div
          className={styles.seed__results}
          role="listbox"
          aria-label="Search results"
        >
          {tracks.map((track) => (
            <button
              key={track.rating_key}
              type="submit"
              name="rating_key"
              value={track.rating_key}
              disabled={analysing}
              className={styles.seed__result}
              role="option"
              aria-selected={false}
              aria-label={`${track.title} by ${track.artist}`}
            >
              <AlbumArt
                src={track.art_url}
                artist={track.artist}
                album={track.album}
              />
              <span className={styles.seed__info}>
                <span className={styles.seed__title}>{track.title}</span>
                <span className={styles.seed__artist}>
                  {track.artist} - {track.album}
                </span>
              </span>
            </button>
          ))}
        </div>
      </Form>

      {query && !tracks.length && !error && (
        <Text tone="muted">No tracks found</Text>
      )}

      <WorkingOverlay
        open={analysing}
        label="Analyzing track"
        steps={STAGES}
        titled
      />
    </div>
  )
}
