/**
 * A timestamp as the history feed and the footer speak it.
 *
 * `frontend/app.js` carried two of these — `relativeTime` at :670 for the feed
 * and `formatRelativeTime` at :2280 for the footer — differing only in whether
 * they wrote "2m ago" or "2 mins ago". One form is kept, the compact one, so
 * the two places cannot drift apart again.
 *
 * `now` is a parameter rather than a `Date.now()` call so the output can be
 * asserted without faking the clock.
 */

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** How long ago, or `Never` when nothing has happened yet. */
export function timeAgo(iso: string | null | undefined, now: Date): string {
  if (!iso) return 'Never'

  const then = new Date(iso)
  const elapsed = now.getTime() - then.getTime()
  const minutes = Math.floor(elapsed / MINUTE)
  const hours = Math.floor(elapsed / HOUR)
  const days = Math.floor(elapsed / DAY)

  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${String(minutes)}m ago`
  if (hours < 24) return `${String(hours)}h ago`
  if (days === 1) return 'Yesterday'
  // Within the week the weekday says more than "5d ago" does.
  if (days < 7) return then.toLocaleDateString(undefined, { weekday: 'long' })
  if (then.getFullYear() === now.getFullYear()) {
    return then.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    })
  }
  return then.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
}
