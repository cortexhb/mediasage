/**
 * The name a playlist is offered under before anyone edits it.
 *
 * Ports `generatePlaylistName` (`frontend/app.js:3148`), which is only reached
 * when the model returned no title of its own.
 */
export function playlistName(prompt: string, on: Date): string {
  const date = on.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
  const words = prompt.split(' ').slice(0, 3).join(' ')
  return `${words}... (${date})`
}
