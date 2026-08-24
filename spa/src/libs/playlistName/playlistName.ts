/**
 * The name a playlist is offered under before anyone edits it.
 *
 * Ports `generatePlaylistName` (`frontend/app.js:3148`), which is only reached
 * when the model returned no title of its own. Both flows name it differently:
 * a prompt flow opens with the words that were typed, a seed flow with the
 * track everything was picked to sound like.
 */
import type { PlaylistFlow } from '../flowStore/flowStore.ts'

export function playlistName(flow: PlaylistFlow, on: Date): string {
  const date = on.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
  if (flow.mode === 'seed') return `Like ${flow.track.title} (${date})`

  const words = flow.prompt.split(' ').slice(0, 3).join(' ')
  return `${words}... (${date})`
}
