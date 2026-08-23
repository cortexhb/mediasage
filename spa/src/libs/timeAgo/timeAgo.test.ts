import { describe, expect, it } from 'vitest'

import { timeAgo } from './timeAgo.ts'

/** A Thursday, so "within the week" has weekdays on both sides of it. */
const NOW = new Date('2026-08-20T12:00:00Z')

/** `iso` for a timestamp `ms` before `NOW`. */
function ago(ms: number): string {
  return new Date(NOW.getTime() - ms).toISOString()
}

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

describe('timeAgo', () => {
  it.each([
    ['nothing at all', null, 'Never'],
    ['an undefined timestamp', undefined, 'Never'],
  ])('says Never for %s', (_case, value, expected) => {
    expect(timeAgo(value, NOW)).toBe(expected)
  })

  it.each([
    [0, 'Just now'],
    [30_000, 'Just now'],
    [MINUTE, '1m ago'],
    [59 * MINUTE, '59m ago'],
    [HOUR, '1h ago'],
    [23 * HOUR, '23h ago'],
    [DAY, 'Yesterday'],
  ])('reports %ims as %s', (elapsed, expected) => {
    expect(timeAgo(ago(elapsed), NOW)).toBe(expected)
  })

  it('names the weekday inside the week, since "5d ago" says less', () => {
    expect(timeAgo(ago(5 * DAY), NOW)).toBe('Saturday')
  })

  it('drops to a date once the weekday stops being unambiguous', () => {
    expect(timeAgo(ago(8 * DAY), NOW)).toBe('Aug 12')
  })

  it('carries the year once it is not this one', () => {
    expect(timeAgo('2025-02-10T12:00:00Z', NOW)).toBe('Feb 2025')
  })
})
