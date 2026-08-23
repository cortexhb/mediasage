/**
 * A saved result's title, as the feed shows it.
 *
 * Playlists are saved with a month-and-year suffix so the Plex playlist is
 * distinguishable from last month's run of the same prompt. In a feed already
 * grouped by date that suffix is noise, so it comes off. Album titles keep
 * theirs: an album's name is its own, not something the app appended.
 *
 * Ported from `frontend/app.js:734`.
 */
import type { ResultListItem } from '../../api/generated/types.gen.ts'

/** ` - Feb 2026`, the shape `backend/generator/models.py:194` appends. */
const SAVED_ON = / - (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}$/

export function historyTitle(item: ResultListItem): string {
  if (item.type === 'album_recommendation') return item.title
  return item.title.replace(SAVED_ON, '')
}
