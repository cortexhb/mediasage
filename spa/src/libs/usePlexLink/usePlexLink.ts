/**
 * The Plex sign-in, as the four states the card can be in.
 *
 * Owns the pin exchange: create a pin, send the user to plex.tv, poll until
 * it comes back approved, then let them pick a server. Everything here is
 * network and timers, which is why it is a hook and not part of the card.
 *
 * The poll is a chain of timeouts rather than an interval: an interval fires
 * again while the previous request is still open, and a slow plex.tv would
 * queue polls behind each other.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  beginPlexLink,
  choosePlexServer,
  forgetPlexLink,
  listPlexServers,
  pollPlexLink,
} from '../../api/plex/plex.ts'
import type {
  PlexLinkedResponse,
  PlexServerChoice,
} from '../../api/generated/types.gen.ts'
import { ApiError } from '../../api/request/request.ts'

/** Milliseconds between polls. Plex's own web client uses one second. */
const POLL_MS = 2000

/** Assumed pin lifetime when plex.tv reports none, in seconds. */
const ASSUMED_LIFETIME = 900

const EXPIRED = 'The sign-in code expired. Start again.'
const UNREACHABLE = 'Could not reach the server.'

/** What went wrong, as something the card can show. */
function reason(failure: unknown): string {
  return failure instanceof ApiError ? failure.message : UNREACHABLE
}

/**
 * Where the card is.
 *
 * `idle` covers both signed out and signed in with a server: which one is
 * read off the configuration, not off this.
 */
export type PlexStage = 'idle' | 'waiting' | 'choosing' | 'busy'

export interface PlexLink {
  readonly stage: PlexStage
  /**
   * Whether a sign-in has happened in this session.
   *
   * Sticky until a sign-out succeeds: between approving the pin and choosing
   * a server the loaded configuration still says signed out, and showing that
   * would call a completed sign-in a failed one.
   */
  readonly signedIn: boolean
  /** The four-character code the user approves. Empty unless waiting. */
  readonly code: string
  /** Where the user approves it, for when a popup was blocked. */
  readonly approvalUrl: string
  readonly servers: readonly PlexServerChoice[]
  /** What choosing a server or signing out left in force. */
  readonly linked: PlexLinkedResponse | undefined
  readonly error: string
  /** Start a pin exchange, sending `target` to plex.tv when it is ready. */
  readonly signIn: (target: Window | null) => void
  readonly choose: (serverId: string) => void
  readonly signOut: () => void
  /** Abandon a pin. */
  readonly cancel: () => void
}

/**
 * Args:
 *   linked: Whether the loaded configuration already holds an account token.
 *     Its servers are listed on mount, so the card offers the choice upfront
 *     rather than behind a button.
 */
export function usePlexLink(linked: boolean): PlexLink {
  const [stage, setStage] = useState<PlexStage>('idle')
  const [pin, setPin] = useState<
    | { readonly id: number; readonly code: string; readonly url: string }
    | undefined
  >()
  const [servers, setServers] = useState<readonly PlexServerChoice[]>([])
  const [kept, setKept] = useState<PlexLinkedResponse | undefined>()
  const [signedIn, setSignedIn] = useState(false)
  const [error, setError] = useState('')

  // One controller for whatever is in flight; unmounting drops it.
  const sending = useRef<AbortController>(null)

  const opening = useCallback((): AbortSignal => {
    sending.current?.abort()
    sending.current = new AbortController()
    return sending.current.signal
  }, [])

  useEffect(() => () => sending.current?.abort(), [])

  const signIn = useCallback(
    (target: Window | null): void => {
      const signal = opening()
      setError('')
      // Not `waiting`: there is no code to wait on yet.
      setStage('busy')

      beginPlexLink(signal).then(
        (started) => {
          setPin({ id: started.pin_id, code: started.code, url: started.url })
          setStage('waiting')
          // Opened before the pin existed: a popup opened later is blocked.
          if (target) target.location.href = started.url
        },
        (failure: unknown) => {
          if (signal.aborted) return
          target?.close()
          setStage('idle')
          setError(reason(failure))
        },
      )
    },
    [opening],
  )

  useEffect(() => {
    if (!pin) return

    const controller = new AbortController()
    const deadline = Date.now() + ASSUMED_LIFETIME * 1000
    let timer = 0

    const ask = async (): Promise<void> => {
      if (Date.now() > deadline) {
        setPin(undefined)
        setStage('idle')
        setError(EXPIRED)
        return
      }

      try {
        const status = await pollPlexLink(pin.id, controller.signal)
        if (status.state !== 'linked') {
          timer = window.setTimeout(poll, POLL_MS)
          return
        }
        setServers(status.servers ?? [])
        setPin(undefined)
        setSignedIn(true)
        setStage('choosing')
      } catch (failure: unknown) {
        if (controller.signal.aborted) return
        setPin(undefined)
        setStage('idle')
        setError(reason(failure))
      }
    }

    /** `ask` never rejects, but the promise still has to be consumed. */
    const poll = (): void => {
      ask().catch(() => undefined)
    }

    // Immediate: a fast approval must not wait a full round.
    poll()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [pin])

  const choose = useCallback(
    (serverId: string): void => {
      const signal = opening()
      setError('')
      setStage('busy')

      choosePlexServer(serverId, signal).then(
        (chosen) => {
          setKept(chosen)
          setStage('idle')
        },
        (failure: unknown) => {
          if (signal.aborted) return
          // Back to the picker: another server on the list may answer.
          setStage('choosing')
          setError(reason(failure))
        },
      )
    },
    [opening],
  )

  const signOut = useCallback((): void => {
    const signal = opening()
    setError('')
    setStage('busy')

    forgetPlexLink(signal).then(
      (forgotten) => {
        setKept(forgotten)
        setServers([])
        setSignedIn(false)
        setStage('idle')
      },
      (failure: unknown) => {
        if (signal.aborted) return
        setStage('idle')
        setError(reason(failure))
      },
    )
  }, [opening])

  useEffect(() => {
    if (!linked) return

    // Its own controller: nothing else in flight may cancel the list.
    const listing = new AbortController()

    listPlexServers(listing.signal).then(
      (listed) => {
        setServers(listed.servers ?? [])
      },
      // Silent: the card still names the server it is connected to.
      () => undefined,
    )

    return () => {
      listing.abort()
    }
  }, [linked])

  const cancel = useCallback((): void => {
    sending.current?.abort()
    setPin(undefined)
    setStage('idle')
    setError('')
  }, [])

  return {
    stage,
    signedIn,
    code: pin?.code ?? '',
    approvalUrl: pin?.url ?? '',
    servers,
    linked: kept,
    error,
    signIn,
    choose,
    signOut,
    cancel,
  }
}
