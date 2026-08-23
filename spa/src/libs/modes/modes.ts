/**
 * The three things the app makes, named.
 *
 * Not in `ModeIcon` beside the shapes it names: a module that exports both a
 * component and a constant loses fast refresh, which the `react-refresh` rule
 * enforces.
 */
import type { ResultListItem } from '../../api/generated/types.gen.ts'

/** What produced a result, which is also what the app can be asked to make. */
export type Mode = ResultListItem['type']

/** What an icon stands for, for the `title` a history entry carries. */
export const MODE_NAMES: Record<Mode, string> = {
  prompt_playlist: 'Playlist from prompt',
  seed_playlist: 'Playlist from seed',
  album_recommendation: 'Album recommendation',
}
