/**
 * Step three of the playlist flow: narrow the library before spending a model.
 *
 * The chips and their counts come from the analysis the refine step bought, so
 * this draws without a read of its own. The preview under them is asked again
 * on every change: `POST /api/filter/preview` counts rows in the local cache
 * and spends nothing.
 *
 * The selection is React state and reaches both the preview and the action
 * through hidden inputs, because a chip is a toggle rather than a form
 * control. One `Form`, so what is previewed is what is submitted.
 */
import { useEffect, useRef, useState } from 'react'
import { Form, useFetcher, useLoaderData, useNavigate } from 'react-router'

import type { FilterPreviewResponse } from '../../api/generated/types.gen.ts'
import { Button } from '../../components/atoms/Button/Button.tsx'
import { Chip } from '../../components/atoms/Chip/Chip.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { CheckboxField } from '../../components/molecules/CheckboxField/CheckboxField.tsx'
import { ChoiceRow } from '../../components/molecules/ChoiceRow/ChoiceRow.tsx'
import { Stepper } from '../../components/molecules/Stepper/Stepper.tsx'
import type { FiltersData } from '../../libs/loadFilters/loadFilters.ts'
import { PREVIEW } from '../../libs/previewSelection/previewSelection.ts'
import { PLAYLIST_STEPS } from '../../libs/playlistSteps/playlistSteps.ts'
import styles from './FiltersStep.module.scss'

const SIZES = [15, 25, 50, 100].map((value) => ({
  value,
  label: String(value),
}))

/** Plex rates out of 10, so a star is two points. */
const RATINGS = [
  { value: 0, label: 'Any' },
  { value: 2, label: '★+' },
  { value: 4, label: '★★+' },
  { value: 6, label: '★★★+' },
  { value: 8, label: '★★★★+' },
]

const LIMITS = [100, 250, 500, 1000].map((value) => ({
  value,
  label: String(value),
}))

const LIMIT_HINT =
  'Limit how many tracks are sent to the AI for selection. Higher = better variety but more cost.'

export function FiltersStep() {
  const { analysis, ceiling } = useLoaderData<FiltersData>()
  const preview = useFetcher<FilterPreviewResponse | null>()
  const navigate = useNavigate()
  const form = useRef<HTMLFormElement>(null)

  const [genres, setGenres] = useState<readonly string[]>(
    analysis.suggested_genres,
  )
  const [decades, setDecades] = useState<readonly string[]>(
    analysis.suggested_decades,
  )
  const [size, setSize] = useState(25)
  const [rating, setRating] = useState(0)
  const [limit, setLimit] = useState(500)
  const [excludeLive, setExcludeLive] = useState(true)

  const allGenres = analysis.available_genres.map((genre) => genre.name)
  const allDecades = analysis.available_decades.map((decade) => decade.name)
  const counts = preview.data

  useEffect(() => {
    const fields = form.current
    if (!fields) return
    // The form itself, so what is counted is what would be submitted.
    preview
      .submit(fields, { method: 'post', action: PREVIEW })
      .catch(() => undefined)
    // `preview` is left out: submitting would then loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genres, decades, size, rating, limit, excludeLive])

  /** Add or remove one name, which is what a chip click means. */
  const toggle = (
    chosen: readonly string[],
    keep: (next: readonly string[]) => void,
    name: string,
  ): void => {
    keep(
      chosen.includes(name)
        ? chosen.filter((each) => each !== name)
        : [...chosen, name],
    )
  }

  /**
   * The no-limit option, named for what no limit actually means here.
   *
   * `frontend/app.js:1454`: the context window caps it anyway, so the button
   * says "All" only while everything matching does fit.
   */
  const uncapped = {
    value: 0,
    label:
      counts && counts.matching_tracks > ceiling
        ? `Max (${ceiling.toLocaleString()})`
        : 'All',
  }

  /** What the preview says, as `frontend/app.js:1429` phrased it. */
  const matching = counts
    ? counts.tracks_to_send < counts.matching_tracks
      ? `${counts.matching_tracks.toLocaleString()} tracks (sending ${counts.tracks_to_send.toLocaleString()} to AI, selected randomly)`
      : `${counts.matching_tracks.toLocaleString()} tracks`
    : '-- matching tracks'

  return (
    <div className={styles.filters}>
      <Stepper steps={PLAYLIST_STEPS} current={3} />

      <Heading level={2}>Filter your library</Heading>
      <p className={styles.filters__description}>
        Select genres and decades to narrow down the tracks sent to the AI.
        Smaller pools mean lower costs and more focused results.
      </p>

      <Form method="post" ref={form}>
        <input type="hidden" name="track_count" value={size} />
        <input type="hidden" name="min_rating" value={rating} />
        <input type="hidden" name="max_tracks_to_ai" value={limit} />
        {genres.map((genre) => (
          <input key={genre} type="hidden" name="genres" value={genre} />
        ))}
        {decades.map((decade) => (
          <input key={decade} type="hidden" name="decades" value={decade} />
        ))}

        <section className={styles.filters__section}>
          <div className={styles.filters__header}>
            <Heading level={3}>Genres</Heading>
            <button
              type="button"
              className={styles.filters__toggleAll}
              aria-label={
                genres.length === allGenres.length
                  ? 'Deselect all genres'
                  : 'Select all genres'
              }
              onClick={() => {
                setGenres(genres.length === allGenres.length ? [] : allGenres)
              }}
            >
              {genres.length === allGenres.length
                ? 'Deselect All'
                : 'Select All'}
            </button>
          </div>
          <div
            className={styles.filters__chips}
            role="group"
            aria-label="Genre filters"
          >
            {analysis.available_genres.map((genre) => (
              <Chip
                key={genre.name}
                selected={genres.includes(genre.name)}
                count={genre.count}
                onChoose={() => {
                  toggle(genres, setGenres, genre.name)
                }}
              >
                {genre.name}
              </Chip>
            ))}
          </div>
        </section>

        <section className={styles.filters__section}>
          <div className={styles.filters__header}>
            <Heading level={3}>Decades</Heading>
            <button
              type="button"
              className={styles.filters__toggleAll}
              aria-label={
                decades.length === allDecades.length
                  ? 'Deselect all decades'
                  : 'Select all decades'
              }
              onClick={() => {
                setDecades(
                  decades.length === allDecades.length ? [] : allDecades,
                )
              }}
            >
              {decades.length === allDecades.length
                ? 'Deselect All'
                : 'Select All'}
            </button>
          </div>
          <div
            className={styles.filters__chips}
            role="group"
            aria-label="Decade filters"
          >
            {analysis.available_decades.map((decade) => (
              <Chip
                key={decade.name}
                selected={decades.includes(decade.name)}
                count={decade.count}
                onChoose={() => {
                  toggle(decades, setDecades, decade.name)
                }}
              >
                {decade.name}
              </Chip>
            ))}
          </div>
        </section>

        <section className={styles.filters__section}>
          <ChoiceRow
            title="Playlist Size"
            spread="even"
            choices={SIZES}
            value={size}
            onChoose={setSize}
          />
        </section>

        <section className={styles.filters__section}>
          <CheckboxField
            label="Exclude live versions"
            name="exclude_live"
            checked={excludeLive}
            onChange={(event) => {
              setExcludeLive(event.target.checked)
            }}
          />
        </section>

        <section className={styles.filters__section}>
          <ChoiceRow
            title="Minimum Rating"
            spread="wrap"
            choices={RATINGS}
            value={rating}
            onChoose={setRating}
          />
        </section>

        <section className={styles.filters__section}>
          <ChoiceRow
            title="Max Tracks to AI"
            hint={LIMIT_HINT}
            spread="wrap"
            choices={[...LIMITS, uncapped]}
            value={limit}
            onChoose={setLimit}
          />
        </section>

        <div className={styles.filters__preview}>
          <span className={styles.filters__matching}>{matching}</span>
        </div>

        <div className={styles.filters__actions}>
          <Button
            variant="secondary"
            onClick={() => {
              Promise.resolve(navigate('/playlist/prompt/refine')).catch(
                () => undefined,
              )
            }}
          >
            Back
          </Button>
          <Button type="submit" variant="primary">
            Generate Playlist
          </Button>
        </div>
      </Form>
    </div>
  )
}
