/**
 * A flow's record, held across a reload and nowhere else.
 *
 * `libs/flowStore` and `libs/albumStore` keep different shapes the same way,
 * and this is that way: one `sessionStorage` key, one version, and a read that
 * answers nothing rather than a broken record.
 *
 * `sessionStorage`, not `localStorage`: a flow belongs to the tab it was
 * started in, and two tabs mid-flow must not overwrite each other.
 *
 * Versioned, because a record's shape will change while old tabs still hold
 * the previous one. A version that does not match is discarded rather than
 * migrated: the cost is one re-analysis, and a migration path for a record
 * that lives minutes is not worth maintaining.
 *
 * Storage itself can throw: Safari's private mode denies access outright.
 */

/** The stored shape: the record, and the version it was written under. */
interface Stored<T> {
  readonly version: number
  readonly flow: T
}

export interface SessionRecord<T> {
  /**
   * The record, or nothing.
   *
   * Answers nothing for a missing record, a version that does not match, and
   * a body that will not parse -- a step cannot act on any of the three, and
   * telling them apart would only give the caller a choice it does not have.
   */
  readonly read: () => T | undefined
  /** Keep the record, or do nothing where storage refuses. */
  readonly write: (flow: T) => void
  readonly forget: () => void
}

/** `version` is bumped by the caller on any change to `T`. */
export function sessionRecord<T>(
  key: string,
  version: number,
): SessionRecord<T> {
  return {
    read: () => {
      let raw: string | null
      try {
        raw = sessionStorage.getItem(key)
      } catch {
        return undefined
      }
      if (raw === null) return undefined

      try {
        const stored = JSON.parse(raw) as Stored<T>
        return stored.version === version ? stored.flow : undefined
      } catch {
        return undefined
      }
    },
    write: (flow) => {
      const stored: Stored<T> = { version, flow }
      try {
        sessionStorage.setItem(key, JSON.stringify(stored))
      } catch {
        // Refused storage costs a re-analysis, not a broken flow.
      }
    },
    forget: () => {
      try {
        sessionStorage.removeItem(key)
      } catch {
        // Nothing to do: the next write replaces it anyway.
      }
    },
  }
}
