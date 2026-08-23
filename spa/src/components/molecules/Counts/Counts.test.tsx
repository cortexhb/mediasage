import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Counts } from './Counts.tsx'

/** What a synced library of some size reports. */
const STATS = {
  total_tracks: 52341,
  genres: [
    { name: 'Rock', count: 900 },
    { name: 'Jazz', count: 120 },
  ],
  decades: [
    { name: '1970s', count: 400 },
    { name: '1980s', count: 620 },
  ],
}

describe('Counts', () => {
  it('labels every count', () => {
    render(<Counts stats={STATS} />)

    for (const label of ['Total Tracks', 'Genres', 'Decades']) {
      expect(screen.getByText(label)).toBeVisible()
    }
  })

  it('separates the thousands, since a raw track count is unreadable', () => {
    render(<Counts stats={STATS} />)

    expect(screen.getByText('52,341')).toBeVisible()
  })

  it('counts the genres rather than listing them', () => {
    render(<Counts stats={STATS} />)

    expect(screen.getByText('2')).toBeVisible()
    expect(screen.queryByText('Rock')).not.toBeInTheDocument()
  })

  it('names the decades, since there are few enough to read', () => {
    render(<Counts stats={STATS} />)

    expect(screen.getByText('1970s, 1980s')).toBeVisible()
  })

  it('reports an empty library without an empty line', () => {
    render(<Counts stats={{ total_tracks: 0, genres: [], decades: [] }} />)

    expect(screen.getByText('None')).toBeVisible()
    expect(screen.getAllByText('0')).toHaveLength(2)
  })
})
