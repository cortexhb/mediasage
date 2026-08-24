/**
 * Generating a playlist, and writing one back to Plex.
 *
 * Generation streams: it makes several LLM calls and the reader is watching.
 * The frames are declared by `PlaylistStreamFrame` in the schema, but the
 * stream itself is read by `readEventStream`, which is frame-agnostic --
 * narrowing is `libs/playlistFrames`.
 *
 * Saving comes in two shapes, as `frontend/app.js:3159` had it: a new
 * playlist, or an existing one replaced or appended to.
 */
import type {
  GenerateRequest,
  PlaylistResult,
  PlaylistUpdateResult,
  PlexPlaylistInfo,
  SavePlaylistRequest,
  UpdatePlaylistRequest,
} from '../generated/types.gen.ts'
import { request, stream } from '../request/request.ts'

/**
 * `POST /api/generate/stream` — a playlist, as a stream of frames.
 *
 * Returns the body unread. A seed track that no longer resolves is a 404
 * before the first frame, so the caller never has to read that from a frame.
 */
export function generatePlaylist(
  body: GenerateRequest,
  signal: AbortSignal,
): Promise<ReadableStream<Uint8Array>> {
  return stream('/api/generate/stream', { method: 'POST', body, signal })
}

/**
 * `POST /api/playlist` — write a generated playlist to Plex.
 *
 * `tracks_skipped` counts keys Plex could not resolve; the playlist is still
 * created from whatever did, so a partial write is not a failure.
 */
export function savePlaylist(
  body: SavePlaylistRequest,
  signal: AbortSignal,
): Promise<PlaylistResult> {
  return request<PlaylistResult>('/api/playlist', {
    method: 'POST',
    body,
    signal,
  })
}

/**
 * `POST /api/playlist/update` — replace or append to an existing playlist.
 *
 * `mode` decides which: `replace` clears the playlist first, `append` adds to
 * what is there. Both answer with what actually landed.
 */
export function updatePlaylist(
  body: UpdatePlaylistRequest,
  signal: AbortSignal,
): Promise<PlaylistUpdateResult> {
  return request<PlaylistUpdateResult>('/api/playlist/update', {
    method: 'POST',
    body,
    signal,
  })
}

/** `GET /api/plex/playlists` — what the replace and append modes pick from. */
export function listPlexPlaylists(
  signal: AbortSignal,
): Promise<PlexPlaylistInfo[]> {
  return request<PlexPlaylistInfo[]>('/api/plex/playlists', { signal })
}
