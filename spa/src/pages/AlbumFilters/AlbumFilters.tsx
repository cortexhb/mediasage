/**
 * Step three of the album flow: pick the mode, narrow the library, choose how
 * much of it a model may see.
 *
 * What starts selected came from the loader -- the prompt's suggestion, or
 * everything. The banner above says which, exactly as `frontend/app.js:4250`
 * decided whether to show it.
 *
 * The preview under the chips is asked again on every change through a
 * fetcher: `GET /api/recommend/albums/preview` counts rows in the local cache
 * and spends nothing.
 */
import { useEffect, useState } from 'react'
import { Form, useFetcher, useLoaderData, useNavigate } from 'react-router'

import type { AlbumPreviewResponse } from '../../api/generated/types.gen.ts'
import { Button } from '../../components/atoms/Button/Button.tsx'
import { Chip } from '../../components/atoms/Chip/Chip.tsx'
import { Heading } from '../../components/atoms/Heading/Heading.tsx'
import { ChoiceRow } from '../../components/molecules/ChoiceRow/ChoiceRow.tsx'
import { ModeSwitch } from '../../components/molecules/ModeSwitch/ModeSwitch.tsx'
import { Stepper } from '../../components/molecules/Stepper/Stepper.tsx'
import { ALBUM_STEPS } from '../../libs/albumSteps/albumSteps.ts'
import { FAMILIARITIES } from '../../libs/familiarityPref/familiarityPref.ts'
import type { AlbumFiltersData } from '../../libs/loadAlbumFilters/loadAlbumFilters.ts'
import { ALBUM_PREVIEW } from '../../libs/previewAlbums/previewAlbums.ts'
import styles from './AlbumFilters.module.scss'

/** `frontend/app.js:1288`, kept whole and cut to the model's ceiling. */
const LIMITS = [1000, 2500, 5000, 10_000, 35_000]

const LIMIT_HINT = 'Limit how many albums are sent to the AI for selection.'

const PRESELECTED = 'Pre-selected based on your prompt. Adjust if needed.'

export function AlbumFilters() {
  const data = useLoaderData<AlbumFiltersData>()
  const preview = useFetcher<AlbumPreviewResponse | null>()
  const navigate = useNavigate()

  const [mode, setMode] = useState(data.mode)
  const [familiarity, setFamiliarity] = useState(data.familiarity)
  const [genres, setGenres] = useState(data.selectedGenres)
  const [decades, setDecades] = useState(data.selectedDecades)
  const [maxAlbums, setMaxAlbums] = useState(Math.min(2500, data.ceiling))

  const allGenres = data.availableGenres.map((genre) => genre.name)
  const allDecades = data.availableDecades.map((decade) => decade.name)
  const counts = preview.data

  useEffect(() => {
    const asked = new URLSearchParams({ max_albums: String(maxAlbums) })
    // All selected is no filter: it would otherwise exclude the untagged.
    if (genres.length && genres.length < allGenres.length)
      asked.set('genres', genres.join(','))
    if (decades.length && decades.length < allDecades.length)
      asked.set('decades', decades.join(','))

    preview.load(`${ALBUM_PREVIEW}?${asked.toString()}`).catch(() => undefined)
    // `preview` is left out: loading would then loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genres, decades, maxAlbums])

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

  /** What the preview says, as `frontend/app.js:4172` phrased it. */
  const matching = counts
    ? counts.albums_to_send < counts.matching_albums
      ? `${counts.matching_albums.toLocaleString()} albums (sending ${counts.albums_to_send.toLocaleString()} to AI)`
      : `${counts.matching_albums.toLocaleString()} albums`
    : '-- albums'

  const choices = [
    ...LIMITS.filter((limit) => limit <= data.ceiling).map((limit) => ({
      value: limit,
      label: limit.toLocaleString(),
    })),
    { value: 0, label: `Max (${data.ceiling.toLocaleString()})` },
  ]

  return (
    <div className={styles.albumFilters}>
      <Stepper steps={ALBUM_STEPS} current={3} />

      {data.fromPrompt && (
        <p className={styles.albumFilters__suggested}>{PRESELECTED}</p>
      )}

      <Form method="post">
        <input type="hidden" name="genre_total" value={allGenres.length} />
        <input type="hidden" name="decade_total" value={allDecades.length} />
        <input type="hidden" name="max_albums" value={maxAlbums} />
        <input type="hidden" name="mode" value={mode} />
        <input type="hidden" name="familiarity" value={familiarity} />
        {genres.map((genre) => (
          <input key={genre} type="hidden" name="genres" value={genre} />
        ))}
        {decades.map((decade) => (
          <input key={decade} type="hidden" name="decades" value={decade} />
        ))}

        <Heading level={2}>Choose your mode</Heading>
        <div className={styles.albumFilters__mode}>
          <ModeSwitch value={mode} onChoose={setMode} />
        </div>

        <section className={styles.albumFilters__section}>
          <div className={styles.albumFilters__header}>
            <Heading level={3}>Genres</Heading>
            <button
              type="button"
              className={styles.albumFilters__toggleAll}
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
            className={styles.albumFilters__chips}
            role="group"
            aria-label="Genre filters"
          >
            {data.availableGenres.map((genre) => (
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

        <section className={styles.albumFilters__section}>
          <div className={styles.albumFilters__header}>
            <Heading level={3}>Decades</Heading>
            <button
              type="button"
              className={styles.albumFilters__toggleAll}
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
            className={styles.albumFilters__chips}
            role="group"
            aria-label="Decade filters"
          >
            {data.availableDecades.map((decade) => (
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

        <section className={styles.albumFilters__section}>
          <ChoiceRow
            title="Max Albums to AI"
            hint={LIMIT_HINT}
            spread="wrap"
            choices={choices}
            value={maxAlbums >= data.ceiling ? 0 : maxAlbums}
            onChoose={(limit) => {
              setMaxAlbums(limit === 0 ? data.ceiling : limit)
            }}
          />
        </section>

        <div className={styles.albumFilters__preview}>
          <span className={styles.albumFilters__matching}>{matching}</span>
        </div>

        <section className={styles.albumFilters__section}>
          <Heading level={3}>Play History</Heading>
          <div
            className={styles.albumFilters__chips}
            role="radiogroup"
            aria-label="Play history preference"
          >
            {FAMILIARITIES.map((each) => (
              <Chip
                key={each.value}
                as="radio"
                selected={each.value === familiarity}
                onChoose={() => {
                  setFamiliarity(each.value)
                }}
              >
                {each.label}
              </Chip>
            ))}
          </div>
          <p className={styles.albumFilters__hint}>
            Influences which albums are suggested
          </p>
        </section>

        <div className={styles.albumFilters__actions}>
          <Button
            variant="secondary"
            onClick={() => {
              Promise.resolve(navigate('/recommend/refine')).catch(
                () => undefined,
              )
            }}
          >
            Back
          </Button>
          <Button type="submit" variant="primary">
            Next
          </Button>
        </div>
      </Form>
    </div>
  )
}
