/**
 * Playing a generated playlist on a Plex device.
 *
 * Two calls, in order: the devices that can be sent a queue, then the queue
 * itself. Nothing is written to the library, so neither is a save.
 */
import type {
  PlayQueueRequest,
  PlayQueueResult,
  PlexClientInfo,
} from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/** `GET /api/plex/clients` — the players the server can see right now. */
export function listPlexClients(
  signal: AbortSignal,
): Promise<PlexClientInfo[]> {
  return request<PlexClientInfo[]>('/api/plex/clients', { signal })
}

/**
 * `POST /api/play-queue` — start these tracks on one device.
 *
 * `error_code` on the result tells an unreachable device from a refused one,
 * which is why a failure is a 200 with a body rather than a status.
 */
export function createPlayQueue(
  body: PlayQueueRequest,
  signal: AbortSignal,
): Promise<PlayQueueResult> {
  return request<PlayQueueResult>('/api/play-queue', {
    method: 'POST',
    body,
    signal,
  })
}
