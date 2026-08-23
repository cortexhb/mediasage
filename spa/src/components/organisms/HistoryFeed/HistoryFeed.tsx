/**
 * Recent activity: what the app has been asked to make, newest first.
 *
 * The first page arrives from the route loader, so the feed never fetches to
 * render. It fetches only when the reader asks for more, and deletes only when
 * the reader asks twice.
 *
 * Filtering is client-side over the page already loaded. `GET /api/results`
 * takes a `type`, but filtering server-side would repaginate under the reader
 * — the counts on the chips would then describe a page nobody is looking at.
 */
import { useEffect, useRef, useState } from 'react'

import type { ResultListItem } from '../../../api/generated/types.gen.ts'
import { forgetResult, listResults } from '../../../api/results/results.ts'
import { Button } from '../../atoms/Button/Button.tsx'
import { Chip } from '../../atoms/Chip/Chip.tsx'
import { HistoryEntry } from '../../molecules/HistoryEntry/HistoryEntry.tsx'
import { Text } from '../../atoms/Text/Text.tsx'
import { dateGroup } from '../../../libs/dateGroup/dateGroup.ts'
import {
  PAGE,
  type HistoryPage,
} from '../../../libs/loadHistory/loadHistory.ts'
import styles from './HistoryFeed.module.scss'

/** How long a first delete click waits for its second. */
const CONFIRM_MS = 3000

/** Which entries a chip admits. */
const FILTERS = {
  all: () => true,
  playlists: (item: ResultListItem) => item.type !== 'album_recommendation',
  albums: (item: ResultListItem) => item.type === 'album_recommendation',
}

type Filter = keyof typeof FILTERS

const LABELS: Record<Filter, string> = {
  all: 'All',
  playlists: 'Playlists',
  albums: 'Albums',
}

/**
 * A signal for a call nothing cancels.
 *
 * A delete and a "load more" are the reader's own click; abandoning either on
 * unmount would leave the server and the screen disagreeing.
 */
function uncancelled(): AbortSignal {
  return new AbortController().signal
}

export interface HistoryFeedProps {
  readonly page: HistoryPage
}

export function HistoryFeed({ page }: HistoryFeedProps) {
  const [items, setItems] = useState<readonly ResultListItem[]>(page.items)
  const [total, setTotal] = useState(page.total)
  const [filter, setFilter] = useState<Filter>('all')
  const [confirming, setConfirming] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // One instant per pass, so no two entries date against different clocks.
  const now = new Date()

  const expiry = useRef(0)
  useEffect(
    () => () => {
      clearTimeout(expiry.current)
    },
    [],
  )

  const armDelete = (id: string): void => {
    clearTimeout(expiry.current)
    setConfirming(id)
    expiry.current = window.setTimeout(() => {
      setConfirming('')
    }, CONFIRM_MS)
  }

  const remove = (id: string): void => {
    if (confirming !== id) {
      armDelete(id)
      return
    }
    clearTimeout(expiry.current)
    setConfirming('')

    // Optimistic: restored only if the server refuses.
    const kept = items
    setItems(items.filter((item) => item.id !== id))
    setTotal(Math.max(0, total - 1))

    forgetResult(id, uncancelled()).catch(() => {
      setItems(kept)
      setTotal(total)
      setError('That could not be deleted.')
    })
  }

  const more = (): void => {
    setLoading(true)
    setError('')

    listResults(PAGE, items.length, uncancelled()).then(
      (next) => {
        setItems([...items, ...(next.results ?? [])])
        setTotal(next.total ?? total)
        setLoading(false)
      },
      () => {
        setError('Could not load more history.')
        setLoading(false)
      },
    )
  }

  if (page.failed) return <Text tone="error">Could not load history.</Text>
  if (items.length === 0) {
    return (
      <Text tone="muted">Your playlist and album history will appear here</Text>
    )
  }

  const shown = items.filter(FILTERS[filter])
  const counts = {
    all: items.length,
    playlists: items.filter(FILTERS.playlists).length,
    albums: items.filter(FILTERS.albums).length,
  }

  // Heading is blank unless the entry opens a new day.
  const rows = shown.map((item, index) => {
    const group = dateGroup(item.created_at, now)
    const before = shown[index - 1]
    const heading =
      before && dateGroup(before.created_at, now) === group ? '' : group
    return { item, heading }
  })

  return (
    <div className={styles.historyFeed}>
      <div
        className={styles.historyFeed__filters}
        role="group"
        aria-label="Filter history by type"
      >
        {(Object.keys(FILTERS) as Filter[]).map((name) => (
          <Chip
            key={name}
            selected={filter === name}
            count={counts[name]}
            onChoose={() => {
              setFilter(name)
            }}
          >
            {LABELS[name]}
          </Chip>
        ))}
      </div>

      {rows.map(({ item, heading }) => (
        <div key={item.id}>
          {heading && <h4 className={styles.historyFeed__group}>{heading}</h4>}
          <HistoryEntry
            item={item}
            confirming={confirming === item.id}
            onDelete={remove}
            now={now}
          />
        </div>
      ))}

      {items.length < total && (
        <div className={styles.historyFeed__more}>
          <Button variant="link" onClick={more} disabled={loading}>
            {loading ? 'Loading…' : 'Load more'}
          </Button>
        </div>
      )}

      {error && (
        <Text tone="error" role="alert">
          {error}
        </Text>
      )}
    </div>
  )
}
