# Configuration

Every MediaSage setting, where it can be set, and what its default means.

## Where Settings Come From

| Source                  | Written by             | Notes                                        |
| ----------------------- | ---------------------- | -------------------------------------------- |
| `config.yaml`           | The operator, by hand  | The deployment's base file. Optional.        |
| `data/config.user.yaml` | The Settings UI        | Lives in the data volume, survives restarts. |
| `.env`                  | The operator, by hand  | Same names as the environment.               |
| `.env.langfuse`         | The operator, by hand  | Tracing keys only.                           |
| Environment variables   | The operator or Docker | Highest precedence of the file sources.      |

Precedence, highest first:

1. `MEDIASAGE_*` environment variables
2. `.env`
3. `LANGFUSE_*` variables and `.env.langfuse` (the `langfuse` section only)
4. `data/config.user.yaml`
5. `config.yaml`
6. Field defaults

A value set in the environment cannot be changed from the UI. The Settings form disables
those fields, and reports them under `from_env`, because a save would be overwritten on the
next boot.

## Environment Variable Names

Prefix `MEDIASAGE_`, section and field joined by a double underscore:

```
MEDIASAGE_LLM__ENDPOINT_URL=http://localhost:11434/v1
MEDIASAGE_LLM__CONTEXT_WINDOW=32768
MEDIASAGE_DEFAULTS__TRACK_COUNT=25
MEDIASAGE_PLEX__MUSIC_LIBRARY=Music
```

Lists are JSON: `MEDIASAGE_PLEX__RETRY_BACKOFF='[1.0, 3.0, 8.0, 20.0]'`.

Every field in every table below is reachable this way, with two exceptions: the Plex
identity fields, which are dropped from the environment entirely, and the `langfuse` section,
which additionally accepts Langfuse's own variable names.

## Minimum Configuration

Only the `llm` section is required, and within it only `provider`, `context_window`, and
either `api_key` (hosted) or `endpoint_url` (local). Without them the app fails at boot
rather than mid-request. `config.example.yaml` is a working starting point; copy it to
`config.yaml`.

Plex needs no configuration file. The address and tokens come from the browser sign-in
described in [docs/plex_login.md](plex_login.md).

## The Settings UI

`/settings` writes to `data/config.user.yaml`. Its groups:

| Group           | Sections                                        |
| --------------- | ----------------------------------------------- |
| Plex            | `plex`                                          |
| AI Provider     | `llm`                                           |
| Library         | `library`, `budget`                             |
| Recommendations | `recommend`, `matching`, `research`, `defaults` |
| Advanced        | `art`, `langfuse`                               |

A save is proved before it is kept. Changing `provider`, `api_key`, `endpoint_url`,
`model_analysis`, `model_generation` or `context_window` probes the provider first; a
failure is a 422 on the form and nothing is written. Editing a price or a threshold spends
no completion.

A saved change rebuilds the Plex or LLM client in place. No restart is needed.

Switching `provider` clears `model_analysis`, `model_generation`, `endpoint_url` and the
four price fields, because they name things the new provider does not serve.
`context_window` is kept.

## Secrets

`llm.api_key`, `langfuse.secret_key`, `plex.token` and `plex.account_token` serialise as
`**********` in `GET /api/config`, and a save logs field names only. `llm_api_key_set` in
the same response is how a form knows a credential is there at all. `langfuse.public_key`
is not a secret: Langfuse publishes it to browsers by design.

`config.yaml` and `data/config.user.yaml` hold credentials in plain text. Both, and any
suffixed copy, are gitignored.

## plex

Connection to the Plex server. The first six fields are written by the browser sign-in, are
shown but never editable, and are ignored wherever the environment offers them.

| Field                | Default                 | Meaning                                                              |
| -------------------- | ----------------------- | -------------------------------------------------------------------- |
| `url`                | `""`                    | Cached server address; re-resolved from `server_id` when it moves.   |
| `token`              | `""`                    | The chosen server's token.                                           |
| `account_token`      | `""`                    | Lists the servers; survives swapping which server is used.           |
| `server_id`          | `""`                    | Plex's `clientIdentifier`, stable while the address is not.          |
| `server_name`        | `""`                    | The signed-in server's name.                                         |
| `client_id`          | `""`                    | Sent as `X-Plex-Client-Identifier`; a new one orphans a Plex device. |
| `music_library`      | `Music`                 | Which Plex library section holds the music. Cannot be blank.         |
| `page_size`          | `1000`                  | Rows per bulk request.                                               |
| `connect_timeout`    | `30.0`                  | Seconds one Plex request may take.                                   |
| `reconnect_cooldown` | `30.0`                  | Seconds before a disconnected client retries.                        |
| `retry_backoff`      | `[1.0, 3.0, 8.0, 20.0]` | Seconds between retries. An empty list disables retrying.            |
| `genre_workers`      | `8`                     | Concurrent genre queries during a sync. Max 64; `1` keeps it serial. |

Timing values track the hardware Plex runs on. A NAS answers a bulk page slower than a
desktop and rides closer to its own limits.

## llm

| Field                    | Default                            | Meaning                                                                                  |
| ------------------------ | ---------------------------------- | ---------------------------------------------------------------------------------------- |
| `provider`               | required                           | `anthropic`, `openai`, `gemini`, `ollama`, or `custom`.                                  |
| `api_key`                | `""`                               | Credential for a hosted provider.                                                        |
| `endpoint_url`           | required for `ollama` and `custom` | Where the local server listens, including any `/v1` suffix.                              |
| `model_analysis`         | `""`                               | Reads the prompt and picks the tracks. The stronger model.                               |
| `model_generation`       | `""`                               | Writes the playlist from the filtered list. A cheaper model does.                        |
| `smart_generation`       | `false`                            | Spend the analysis model on generation too.                                              |
| `context_window`         | required                           | Tokens the model accepts. 512 to 2,000,000.                                              |
| `request_timeout`        | `600.0`                            | Seconds before an outbound call is abandoned.                                            |
| `stream_idle_timeout`    | `600.0`                            | Seconds of silence on a generate stream before the browser gives up. Measured per frame. |
| `max_output_tokens`      | `8192`                             | Ceiling on one completion.                                                               |
| `max_retries`            | `3`                                | Attempts per call, with exponential backoff. 1 to 10.                                    |
| `probe_timeout`          | `5.0`                              | Seconds for a metadata-only liveness probe.                                              |
| `temperature`            | unset                              | 0.0 to 2.0.                                                                              |
| `top_p`                  | unset                              | Above 0.0, up to 1.0.                                                                    |
| `top_k`                  | unset                              | 0 or more.                                                                               |
| `min_p`                  | unset                              | 0.0 to 1.0.                                                                              |
| `presence_penalty`       | unset                              | -2.0 to 2.0.                                                                             |
| `repetition_penalty`     | unset                              | Above 0.0, up to 2.0.                                                                    |
| `cost_analysis_input`    | `0.0`                              | USD per million input tokens, analysis model.                                            |
| `cost_analysis_output`   | `0.0`                              | USD per million output tokens, analysis model.                                           |
| `cost_generation_input`  | `0.0`                              | USD per million input tokens, generation model.                                          |
| `cost_generation_output` | `0.0`                              | USD per million output tokens, generation model.                                         |

An unset sampling field sends nothing, leaving the server's own default. A price of `0.0`
makes the UI report no cost rather than a wrong one; local providers always report zero.

`context_window` is required of every provider. There is no per-model limits table in the
code: one goes stale, and a guessed window overflows the model. Ollama is the exception —
the settings form reads the window from `/api/show` and fills the field in.

`anthropic`, `openai` and `gemini` are reached by `api_key`. `ollama` and `custom` are
reached by `endpoint_url`, with `api_key` optional. `custom` covers any OpenAI-compatible
server: MLX, LM Studio, OpenRouter, vLLM.

Token counts reported after a call are the ones the provider returned, not estimates. See
[docs/token_accounting.md](token_accounting.md).

## budget

How much of the library fits in one prompt. The per-item figures are measured averages for
one library line, February 2026; they drive pre-flight budgeting only.

| Field                     | Default | Meaning                                                    |
| ------------------------- | ------- | ---------------------------------------------------------- |
| `tokens_per_track`        | `40`    | Average tokens in one track line. Longer titles need more. |
| `tokens_per_album`        | `25`    | Average tokens in one album line.                          |
| `context_buffer_fraction` | `0.10`  | Room for tokenizer drift. Below 1.0.                       |
| `reserved_prompt_tokens`  | `1000`  | Room for the system prompt and the model's answer.         |

## library

| Field                   | Default                                 | Meaning                                                      |
| ----------------------- | --------------------------------------- | ------------------------------------------------------------ |
| `sync_batch_size`       | `500`                                   | Rows per transaction, and how often the resume point moves.  |
| `stale_after_hours`     | `24`                                    | Hours before the cache is worth re-syncing.                  |
| `stats_cache_seconds`   | `600.0`                                 | Seconds a live stats read is reused. `0` disables it.        |
| `well_loved_avg_plays`  | `3.0`                                   | Average plays per track at which an album counts well-loved. |
| `live_keywords`         | `["live", "concert", "sbd", "bootleg"]` | Words that mark a recording as a live performance.           |
| `dated_titles_are_live` | `true`                                  | Whether a date in the title also marks it live.              |

Plex takes 8.75s aggregating track genres over an 80k library, which is what
`stats_cache_seconds` exists to avoid repeating.

## matching

Floors for matching a name the model returned against the library. Scores are rapidfuzz
ratios over accent-folded, punctuation-stripped text, 0 to 100. Too low plays the wrong
record; too high drops good matches. Clean tags tolerate a high floor; a library full of
`(Remastered)` suffixes needs a lower one.

| Field                | Default | Meaning                                    |
| -------------------- | ------- | ------------------------------------------ |
| `track_threshold`    | `60`    | Matching a named track to the library.     |
| `album_artist_min`   | `70`    | Artist floor when picking a library album. |
| `album_combined_min` | `70`    | Artist and title scored together.          |
| `pitch_artist_min`   | `80`    | Artist floor when attaching a pitch.       |
| `pitch_album_min`    | `60`    | Album-title floor when attaching a pitch.  |

## recommend

The shape of one recommendation round. Sessions live in memory, so the caps are a memory
budget.

| Field                  | Default | Meaning                                                             |
| ---------------------- | ------- | ------------------------------------------------------------------- |
| `session_expiry`       | `1800`  | Seconds an untouched session survives.                              |
| `max_sessions`         | `100`   | Sessions held in memory at once, across all users.                  |
| `recent_limit`         | `30`    | Albums remembered per session, so "Show me another" varies.         |
| `question_count`       | `2`     | Dimensions a round asks about before picking.                       |
| `pick_count`           | `3`     | Albums a round shows: one primary, the rest secondary.              |
| `discovery_request`    | `7`     | Discovery asks for more than it shows; owned albums filtered after. |
| `small_pool`           | `10`    | Below this many candidates the model is told the pool is thin.      |
| `max_exclusion_albums` | `2500`  | Owned albums listed in the discovery prompt.                        |
| `genres_per_line`      | `3`     | Genres per album line; more is noise the model ignores.             |

## research

External sources consulted about an album. MusicBrainz and the Cover Art Archive both
publish mirrors a self-hoster can run, which is why the endpoints are settings.

| Field                     | Default                              | Meaning                                                                                              |
| ------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `request_timeout`         | `10.0`                               | Seconds one research call may take.                                                                  |
| `musicbrainz_url`         | `https://musicbrainz.org/ws/2`       | Point at a local mirror if one is running.                                                           |
| `cover_art_url`           | `https://coverartarchive.org`        | Point at a local mirror if one is running.                                                           |
| `wikipedia_api_url`       | `https://en.wikipedia.org/w/api.php` | A different language edition changes which articles are read.                                        |
| `musicbrainz_interval`    | `1.0`                                | Seconds between MusicBrainz calls; their published limit is one a second. `0` against a mirror.      |
| `wikipedia_max_chars`     | `8000`                               | Characters kept from one article.                                                                    |
| `wikipedia_drop_sections` | 19 section-title fragments           | A section whose title contains any of these is dropped. Full list at `backend/config/models.py:533`. |
| `max_reviews`             | `2`                                  | Reviews read per album. `0` skips reviews.                                                           |
| `review_max_chars`        | `2000`                               | Characters kept from one review.                                                                     |
| `review_min_chars`        | `1500`                               | Earliest character a sentence break is accepted at when trimming. Cannot exceed `review_max_chars`.  |
| `blocked_review_hosts`    | `["allmusic.com"]`                   | Never fetched. AllMusic's terms prohibit automated access.                                           |
| `max_redirects`           | `5`                                  | Redirect hops followed; each is re-checked as safe.                                                  |

## art

The backend proxies album art so the Plex token never reaches the browser.

| Field                    | Default                                  | Meaning                                                      |
| ------------------------ | ---------------------------------------- | ------------------------------------------------------------ |
| `timeout`                | `10.0`                                   | Seconds an art fetch may take.                               |
| `cache_max_age`          | `604800`                                 | Seconds a browser may reuse Plex art. Seven days.            |
| `external_cache_max_age` | `86400`                                  | Seconds a browser may reuse external art. One day.           |
| `external_domains`       | `["coverartarchive.org", "archive.org"]` | Hosts external art may be fetched from, subdomains included. |
| `max_redirects`          | `5`                                      | Redirect hops followed.                                      |

Plex mints a new thumb path when artwork changes, so its art is content-addressed and can be
cached hard. External art carries no content address and gets less.

## defaults

| Field         | Default | Meaning                                              |
| ------------- | ------- | ---------------------------------------------------- |
| `track_count` | `25`    | Playlist length the create forms open on. 1 to 1000. |

## langfuse

LLM tracing. Off until `base_url`, `public_key` and `secret_key` are all set. There is no
default endpoint: an unconfigured deployment must not send prompts to a cloud it never chose.

| Field         | Default | Meaning                                                                |
| ------------- | ------- | ---------------------------------------------------------------------- |
| `base_url`    | `""`    | A Langfuse cloud region, or a self-hosted URL.                         |
| `public_key`  | `""`    | The project's public key.                                              |
| `secret_key`  | `""`    | The project's secret key.                                              |
| `environment` | `""`    | Which Langfuse environment traces land in. Empty leaves the SDK's own. |

Also readable under Langfuse's own names, from the environment or from `.env.langfuse`:
`LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_TRACING_ENVIRONMENT`. An explicit `MEDIASAGE_LANGFUSE__*` wins over these. Setup
in [docs/langfuse_tracing.md](langfuse_tracing.md).

## Variables Outside the Config Model

| Variable                                                                                | Default | Effect                                                                                                                                             |
| --------------------------------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MEDIASAGE_LOG_LEVEL`                                                                   | `INFO`  | Python log level by name. An unknown name falls back to `INFO`.                                                                                    |
| `UVICORN_WORKERS`                                                                       | `1`     | Worker processes the container starts.                                                                                                             |
| `APP_VERSION`                                                                           | `dev`   | Version the UI reports. Set from the build arg `VERSION`.                                                                                          |
| `PLEXAPI_PLEXAPI_AUTORELOAD`                                                            | `false` | Set by the app before plexapi imports. Left on, a missing attribute triggers a full refetch per object and a large sync overloads the Plex server. |
| `PLEXAPI_PLEXAPI_CONTAINER_SIZE`                                                        | `1000`  | Set by the app to match `plex.page_size`.                                                                                                          |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OLLAMA_URL`, `CUSTOM_LLM_URL` | unset   | Not read as settings. Their presence is reported to the setup wizard so it can say a value came from the deployment.                               |

Both `PLEXAPI_*` variables use `setdefault`, so an explicitly exported value wins.

## Files and Paths

| Path                    | Contents                                              |
| ----------------------- | ----------------------------------------------------- |
| `config.yaml`           | The base file. Not created by the app.                |
| `config.example.yaml`   | A copyable starting point.                            |
| `data/config.user.yaml` | Settings saved from the UI.                           |
| `data/library_cache.db` | The SQLite mirror of the Plex library. Path is fixed. |
| `.env`, `.env.langfuse` | Environment files, read at boot.                      |

Under Docker, `./data` is bind-mounted to `/app/data` and must be writable by UID 1000. A
save that cannot write the file returns a 500 naming the permission problem, and nothing is
published in memory — the process never runs on settings that are not on disk.

Saving prunes blank and null values rather than writing them, so a cleared field falls back
to its default instead of shadowing it.
