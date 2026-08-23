/**
 * The Plex sign-in endpoints, paired with their generated types.
 *
 * The only way the app gets a Plex token: there is no URL field and no token
 * field. A pin is created here, approved by the user on plex.tv, and polled
 * until it comes back with a server list. See `docs/plex_login.md`.
 */
import type {
  PlexLinkedResponse,
  PlexLinkResponse,
  PlexLinkStatusResponse,
} from '../generated/types.gen.ts'
import { request } from '../request/request.ts'

/** `POST /api/plex/link` — a pin, and the address the user approves it at. */
export function beginPlexLink(signal: AbortSignal): Promise<PlexLinkResponse> {
  return request<PlexLinkResponse>('/api/plex/link', {
    method: 'POST',
    signal,
  })
}

/**
 * `GET /api/plex/link/{pin_id}` — pending, or signed in with the servers.
 *
 * Polled. Answers 502 once the pin has expired, which ends the poll rather
 * than repeating it.
 */
export function pollPlexLink(
  pinId: number,
  signal: AbortSignal,
): Promise<PlexLinkStatusResponse> {
  return request<PlexLinkStatusResponse>('/api/plex/link/{pin_id}', {
    path: { pin_id: pinId },
    signal,
  })
}

/**
 * `GET /api/plex/servers` — the account's servers, listed again.
 *
 * Where the picker comes back from after a reload: the list arrives with the
 * poll, and a closed tab would otherwise cost a second sign-in.
 */
export function listPlexServers(
  signal: AbortSignal,
): Promise<PlexLinkStatusResponse> {
  return request<PlexLinkStatusResponse>('/api/plex/servers', { signal })
}

/**
 * `POST /api/plex/server` — resolve one server's address and connect to it.
 *
 * Answers 422 when none of its addresses answered, which leaves whatever was
 * configured before still in force.
 */
export function choosePlexServer(
  serverId: string,
  signal: AbortSignal,
): Promise<PlexLinkedResponse> {
  return request<PlexLinkedResponse>('/api/plex/server', {
    method: 'POST',
    body: { server_id: serverId },
    signal,
  })
}

/** `DELETE /api/plex/link` — forget the sign-in, keeping the track cache. */
export function forgetPlexLink(
  signal: AbortSignal,
): Promise<PlexLinkedResponse> {
  return request<PlexLinkedResponse>('/api/plex/link', {
    method: 'DELETE',
    signal,
  })
}
