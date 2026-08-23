# Plex Login

Replaces manual Plex configuration with a browser sign-in. After this change there is no Plex server
URL field and no Plex token field: signing in to Plex is the only way the application reaches a
server. Scheduled after Phase 2 of the SPA migration (`spa/docs/migration.md`), because it rewrites
the Plex half of the Settings screen.

Assumes plexapi 4.18.2 (`pyproject.toml:12`) and the configuration loader described in
`backend/config/settings.py`.

## The Flow Plex Offers

Plex's sign-in is a PIN exchange, not OAuth 2. Three steps:

1. `POST https://plex.tv/api/v2/pins?strong=true` returns an `id` and a four-character `code`.
2. The user approves at `https://app.plex.tv/auth#?clientID=…&code=…&forwardUrl=…`.
3. `GET https://plex.tv/api/v2/pins/{id}` returns `authToken` once approved, and nothing before that.

`X-Plex-Product` and `X-Plex-Client-Identifier` are required on every call.

plexapi implements this as `MyPlexPinLogin(oauth=True)` (`plexapi/myplex.py:1724`). It produces an
ordinary long-lived `X-Plex-Token` — the same credential `PlexConfig.token`
(`backend/config/models.py:64`) already holds, so nothing downstream of the configuration changes.

`MyPlexJWTLogin` (`plexapi/myplex.py:1970`) is the other option and is **not** used. It requires
`pyjwt[crypto]`, an ED25519 keypair on disk, and introduces token expiry with a refresh cycle. None
of that buys anything here.

### The Client Identifier Must Persist

plexapi defaults `X-Plex-Client-Identifier` to `hex(getnode())` — the MAC address
(`plexapi/__init__.py:34`). In a container that changes whenever the container is recreated, and a
changing identifier registers a new device on every sign-in, orphaning the previous ones in the
user's Plex account.

A `uuid4` is generated once, persisted as `plex.client_id`, and passed in through the `headers`
argument of `MyPlexPinLogin`.

### Polling Without a Thread

`MyPlexPinLogin.run()` starts a thread. It is not used: the SPA polls, and the poll needs only the
pin id and the stored client identifier, both of which the server already has. That makes the poll
route stateless, so a restart mid-sign-in loses nothing. It is one hand-written call to
`GET /api/v2/pins/{id}`, justified the same way `backend/llm/ollama.py` wraps Ollama's admin API by
hand.

## Configuration After the Change

`PlexConfig` (`backend/config/models.py:56`) gains `client_id`, `account_token`, `server_id` and
`server_name`; keeps `token`, `url` and `music_library`; and loses every one of them as a form field
except `music_library`.

**Two tokens, because they are different credentials.** `MyPlexResource.connect()` authenticates with
the per-resource `accessToken`, not the account token (`plexapi/myplex.py:1601`). The two coincide
for a server the user owns and diverge for one shared with them, so both are stored: `account_token`
lists the servers, `token` talks to the chosen one.

**`url` stops being a setting and becomes a cache.** Addresses move — DHCP, relay, remote access
being toggled. With `server_id` stored, a failed connection re-resolves the address through
`MyPlexAccount.resources()` (`plexapi/myplex.py:313`), whose ordering already prefers local over
remote over relay (`plexapi/myplex.py:1459`). The cached URL is overwritten only once the
replacement connects, per the rule in `CLAUDE.md` against destroying cached state before its
replacement succeeds. Keeping it also means the application still runs when plex.tv is unreachable.

## Environment Variables

Every field is reachable as `MEDIASAGE_<SECTION>__<FIELD>` because `env_prefix` and
`env_nested_delimiter` are set globally (`backend/config/settings.py:54-55`). pydantic-settings has
no per-field opt-out, so removing the Plex identity variables means overriding
`settings_customise_sources` to wrap the environment source and drop those keys.

Removed: `MEDIASAGE_PLEX__URL`, `MEDIASAGE_PLEX__TOKEN`, `MEDIASAGE_PLEX__ACCOUNT_TOKEN`,
`MEDIASAGE_PLEX__SERVER_ID`.

Retained: `MEDIASAGE_PLEX__MUSIC_LIBRARY` and the tuning fields, which are deployment properties
rather than identity.

**Headless Plex configuration ends here.** A container given only environment variables cannot reach
Plex; someone must open the UI and complete a browser sign-in once. This is the one irreversible
consequence of the change.

## Routes

| Route                     | Purpose                                                           |
| ------------------------- | ----------------------------------------------------------------- |
| `POST /api/plex/link`     | Create a pin. Returns its id, the approval URL, and its lifetime. |
| `GET /api/plex/link/{id}` | Pending, expired, or signed in — with the server list on success. |
| `GET /api/plex/servers`   | List the servers again, for a reload between the two.             |
| `POST /api/plex/server`   | Choose a server: resolve, connect, save, rebuild the client.      |
| `DELETE /api/plex/link`   | Clear the stored identity.                                        |

`GET /api/plex/servers` exists because the list otherwise only ever arrives with the poll. The card
calls it on mount whenever a sign-in is already stored, so the server is a select that is always
present rather than something behind a button; it also covers a browser closed between approving the
pin and choosing a server. It answers 409 before a sign-in, and an empty list rather than an error
when plex.tv will not enumerate them — the token is already stored, so that is a retry, not a failed
sign-in.

`ConfigResponse.plex_server_id` and `PlexLinkedResponse.server_id` exist for that select: without
the id it can name the current server but cannot mark it.

`DELETE` clears `account_token`, `token`, `server_id`, `server_name` and `url`. It leaves the track
cache alone: signing out of Plex is not a request to discard a synced library.

`POST /api/setup/validate-plex` (`backend/api/routes/setup/plex.py`) is deleted along with
`ValidatePlexRequest` and `ValidatePlexResponse`. `PlexProbe` stops proving a typed URL and token and
becomes a check that the saved server still answers.

## Contract Changes Reaching the SPA

- `SetupStatusResponse.plex_from_env` is removed. It is computed today from a bare `PLEX_URL`
  (`backend/api/routes/setup/status.py:48`) that nothing else in `backend/` reads — the loader reads
  `MEDIASAGE_PLEX__URL` — so the flag is wrong in both directions. Deleting the field retires the
  defect with it.
- `ConfigResponse` trades `plex_url` and `plex_token_set` for `plex_linked`, `plex_server_name` and
  `plex_server_id`.
- `ConfigUpdate` loses `plex_url` and `plex_token` (`backend/config/models.py:446-447`, and their
  entries in the two mappings at `:427` and `:463`), leaving `music_library` as the only Plex value a
  form writes.

The Settings screen's Plex card becomes: sign-in state, a server picker, a library picker, and a
sign-out action. It is `spa/src/components/organisms/PlexSettings/`, over the state machine in
`spa/src/libs/usePlexLink/`.

**The card must never report a sign-in in progress as signed out.** `ConfigResponse.plex_linked`
comes from the loader, which ran before the sign-in; between approving the pin and the chosen
server being resolved it still says `false`. Two things stop that surfacing: `usePlexLink` keeps a
`signedIn` flag that is sticky until a sign-out succeeds, and every in-flight call renders its own
`busy` state rather than falling through to the signed-out branch.

## Existing Installations

Nothing is migrated and nothing breaks. A `config.yaml` that already holds a URL and token keeps
working, because both fields survive; they simply stop being editable. Changing server means signing
in.

## Security

The application has no authentication and relies on network security. Anyone who can reach it can
start a sign-in, but the token only arrives if the owner approves it in their own browser, and it is
the owner's own token. That is the same trust boundary as today, where anyone who can reach the
application can already `POST /api/config`.

## Sources

- [Authenticating with Plex](https://forums.plex.tv/t/authenticating-with-plex/609370) — read
  2026-08-23; the pin endpoints, the required headers, and the instruction to store and re-use the
  client identifier.
