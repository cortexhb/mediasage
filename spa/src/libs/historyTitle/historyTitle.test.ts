import { describe, expect, it } from 'vitest'

import type { ResultListItem } from '../../api/generated/types.gen.ts'
import { historyTitle } from './historyTitle.ts'

/** A saved result with only the fields this reads set meaningfully. */
function saved(
  title: string,
  type: ResultListItem['type'] = 'prompt_playlist',
): ResultListItem {
  return {
    id: 'a',
    title,
    type,
    prompt: '',
    track_count: 0,
    created_at: '2026-08-20T12:00:00Z',
  }
}

describe('historyTitle', () => {
  it('drops the month the playlist was saved in', () => {
    expect(historyTitle(saved('Rainy Sunday - Feb 2026'))).toBe('Rainy Sunday')
  })

  it('drops it from a seed playlist too', () => {
    expect(historyTitle(saved('Like This - Dec 2025', 'seed_playlist'))).toBe(
      'Like This',
    )
  })

  it('keeps an album title whole, since the app did not write it', () => {
    expect(historyTitle(saved('Live - Aug 2019', 'album_recommendation'))).toBe(
      'Live - Aug 2019',
    )
  })

  it.each([
    ['a month in the middle', 'Feb 2026 - Best Of'],
    ['a year without a month', 'Something - 2026'],
    ['a month without a year', 'Something - Feb'],
    ['no suffix at all', 'Just A Title'],
  ])('leaves %s alone', (_case, title) => {
    expect(historyTitle(saved(title))).toBe(title)
  })
})
