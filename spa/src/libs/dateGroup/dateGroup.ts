/**
 * The heading a history entry sits under.
 *
 * Ported from `frontend/app.js:693`. Boundaries are local calendar days, not
 * elapsed hours: something saved at 23:59 is "Yesterday" a minute later, which
 * is what a reader scanning a feed expects.
 *
 * `now` is a parameter rather than a `Date.now()` call so the output can be
 * asserted without faking the clock.
 */

/** Midnight at the start of `now`'s own day, in local time. */
function startOfDay(now: Date): Date {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

export function dateGroup(iso: string, now: Date): string {
  const then = new Date(iso)
  const today = startOfDay(now)
  if (then >= today) return 'Today'

  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (then >= yesterday) return 'Yesterday'

  // ISO weeks start on Monday, which `getDay` numbers 1 and Sunday 0.
  const weekday = now.getDay() || 7
  const monday = new Date(today)
  monday.setDate(monday.getDate() - weekday + 1)
  if (then >= monday) return 'Earlier this week'

  if (then.getFullYear() === now.getFullYear()) {
    return then.toLocaleDateString(undefined, { month: 'long', day: 'numeric' })
  }
  return then.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}
