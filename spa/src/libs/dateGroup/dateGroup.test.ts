import { describe, expect, it } from 'vitest'

import { dateGroup } from './dateGroup.ts'

/**
 * A Thursday at noon, local time.
 *
 * Local rather than UTC because the boundaries are calendar days: a UTC
 * literal would put "yesterday" on a different side of midnight depending on
 * where the suite runs.
 */
const NOW = new Date(2026, 7, 20, 12, 0, 0)

/** A local timestamp `days` before `NOW`, at `hour`. */
function on(days: number, hour = 12): string {
  const when = new Date(NOW)
  when.setDate(when.getDate() - days)
  when.setHours(hour, 0, 0, 0)
  return when.toISOString()
}

describe('dateGroup', () => {
  it('heads the current day Today', () => {
    expect(dateGroup(on(0), NOW)).toBe('Today')
  })

  it('counts a calendar day, not 24 hours', () => {
    // A minute before midnight is Yesterday, however recent it is.
    expect(dateGroup(on(0, 0), NOW)).toBe('Today')
    expect(dateGroup(on(1, 23), NOW)).toBe('Yesterday')
  })

  it('gathers the rest of the week under one heading', () => {
    // Thursday, so Monday and Tuesday are both still this week.
    expect(dateGroup(on(2), NOW)).toBe('Earlier this week')
    expect(dateGroup(on(3), NOW)).toBe('Earlier this week')
  })

  it('names the day once the week has turned', () => {
    expect(dateGroup(on(9), NOW)).toBe('August 11')
  })

  it('drops the day and keeps the year for another year', () => {
    expect(dateGroup(new Date(2025, 1, 10).toISOString(), NOW)).toBe(
      'February 2025',
    )
  })
})
