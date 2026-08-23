import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { ResultListItem } from '../../../api/generated/types.gen.ts'
import { HistoryEntry, type HistoryEntryProps } from './HistoryEntry.tsx'

const NOW = new Date('2026-08-20T12:00:00Z')

const ITEM: ResultListItem = {
  id: 'e7c1',
  title: 'Rainy Sunday - Feb 2026',
  prompt: 'something for a wet afternoon',
  track_count: 24,
  subtitle: '24 tracks',
  created_at: '2026-08-20T11:00:00Z',
  type: 'prompt_playlist',
}

/** The entry inside a router, since its title is a link. */
function renderEntry(props: Partial<HistoryEntryProps> = {}) {
  const router = createMemoryRouter([
    {
      index: true,
      Component: () => (
        <HistoryEntry
          item={ITEM}
          confirming={false}
          onDelete={vi.fn()}
          now={NOW}
          {...props}
        />
      ),
    },
  ])
  return render(<RouterProvider router={router} />)
}

describe('HistoryEntry', () => {
  it('opens the saved result', () => {
    renderEntry()

    expect(screen.getByRole('link', { name: 'Rainy Sunday' })).toHaveAttribute(
      'href',
      '/result/e7c1',
    )
  })

  it('drops the month the playlist was saved in', () => {
    renderEntry()

    expect(screen.queryByText(/Feb 2026/)).not.toBeInTheDocument()
  })

  it('says how long ago it was made', () => {
    renderEntry()

    expect(screen.getByText('1h ago')).toBeVisible()
  })

  it('names the artist on a seed playlist', () => {
    renderEntry({
      item: { ...ITEM, type: 'seed_playlist', artist: 'Nick Drake' },
    })

    expect(screen.getByText('Nick Drake')).toBeVisible()
  })

  it('leaves an album its own artist line, which is already in the title', () => {
    renderEntry({
      item: { ...ITEM, type: 'album_recommendation', artist: 'Nick Drake' },
    })

    expect(screen.queryByText('Nick Drake')).not.toBeInTheDocument()
  })

  it('falls back to the prompt when nothing summarised it', () => {
    renderEntry({ item: { ...ITEM, subtitle: null } })

    expect(screen.getByText('something for a wet afternoon')).toBeVisible()
  })

  it('names what it would delete, since every row has such a button', () => {
    // In the document, not visible: it is revealed on hover and on
    // `:focus-within`, so it reaches a keyboard without cluttering the feed.
    renderEntry()

    expect(
      screen.getByRole('button', { name: 'Delete Rainy Sunday - Feb 2026' }),
    ).toBeInTheDocument()
  })

  it('asks again once armed, rather than deleting on one click', () => {
    renderEntry({ confirming: true })

    expect(
      screen.getByRole('button', {
        name: 'Confirm deleting Rainy Sunday - Feb 2026',
      }),
    ).toHaveTextContent('Delete?')
  })

  it('hands the id back, so the feed decides which click this is', async () => {
    const deleted = vi.fn()
    renderEntry({ onDelete: deleted })

    await userEvent.click(screen.getByRole('button', { name: /^Delete/ }))

    expect(deleted).toHaveBeenCalledWith('e7c1')
  })

  it('names the icon, which is the only thing marking the kind', () => {
    renderEntry({ item: { ...ITEM, type: 'album_recommendation' } })

    expect(screen.getByTitle('Album recommendation')).toBeInTheDocument()
  })
})
