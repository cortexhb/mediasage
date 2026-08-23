# MediaSage — Requested Work

Running list of what was asked for, in the order it was raised.

---

## 1. Backend performance audit

**Status:** done

Investigate reported backend slowness.

### Findings

| # | Issue | Location |
|---|---|---|
| 1 | `plexapi` `autoreload=true` refetches each object when an attribute is missing from a listing. Plex omits `userRating`/`viewCount`/`lastViewedAt` on unrated/unplayed items and Genre tags on album listings, so a 30k-track sync becomes ~30k extra sequential requests. `getattr(obj, x, default)` does **not** suppress it — plexapi sets missing attributes to `None`, so no `AttributeError` is raised. | `plex_client.py` |
| 2 | `container_size` left at the default 50 — the base listing alone costs one round trip per 50 rows. | `plex_client.py` |
| 3 | Genres stored as a JSON text column, so every genre filter degrades to a full table scan plus `json.loads` per row in Python. Hits `count_tracks_by_filters`, `get_tracks_by_filters`, `get_cached_genre_decade_stats`, `get_album_candidates`. | `library_cache.py` |
| 4 | `get_tracks_by_filters` skipped its SQL `LIMIT` entirely whenever a genre filter was set. | `library_cache.py` |
| 5 | `get_db_connection` opened a fresh connection and re-ran `PRAGMA journal_mode=WAL` per call; that pragma briefly locks the file. Several functions opened two connections per call. | `library_cache.py` |
| 6 | Art proxy returns no `Cache-Control`/`ETag`, so browsers refetch every cover on every render. Each hit costs a `fetchItem` round trip plus the image fetch — a 50-album grid is ~100 Plex requests per page view. | `main.py` |

### Fixes agreed

- [x] Set `PLEXAPI_PLEXAPI_AUTORELOAD=false` and `PLEXAPI_PLEXAPI_CONTAINER_SIZE=1000` before the plexapi import
- [x] Fetch album genres via one query per genre choice instead of per-album attribute access
- [x] Page bulk track/album fetches with retry and exponential backoff on transient errors
- [x] Normalized `track_genres` table + index; rewrite filter/count/stats/album queries to use SQL
- [x] Backfill `track_genres` from the existing JSON column so upgrades do not force a re-sync
- [x] Thread-local connection reuse, pragmas applied once
- [x] `Cache-Control`/`ETag` (with 304 handling) on `/api/art/{rating_key}`; `/api/external-art` already had one
- [x] Unit tests for all of the above

---

## 2. Sync fails on "server overloaded" and loses progress

**Status:** done

`sync_library` committed `DELETE FROM tracks` and `track_count = 0` **before** fetching from Plex. A failed fetch left the cache empty with nothing recorded, and there was no cursor, so a restart refetched from zero. No retry or backoff either — a single transient 503 killed the whole sync.

- [x] Drop the pre-fetch delete; sweep stale rows only after a successful sync, matched on a per-run sync token
- [x] Checkpoint the page offset to `sync_state` so a failed sync resumes instead of restarting
- [x] Retry with exponential backoff on transient Plex errors
- [x] Unit tests

---

## 3. Convert to a uv project

**Status:** done

- [x] `pyproject.toml` with project metadata, dependencies, and dev group
- [x] `uv.lock` generated
- [x] Dockerfile builds with `uv sync --locked --no-dev` (verified: `docker build` exits 0)
- [x] `requirements*.txt` / `requirements*.in` removed
- [x] Commands updated in `CLAUDE.md` and `README.md`
- [x] Targets Python 3.14

---

## 4. Update dependencies

**Status:** done

The pinned set turned out to be closer to current than expected — the old `requirements.txt` was a
`pip-compile` lock. Re-resolving from scratch with uv picked up the drift (`uvicorn` 0.40 to 0.52,
`websockets` 15 to 16, `urllib3`, `typing-extensions`, and others).

- [x] Re-resolved every dependency to latest via `uv lock`
- [x] Full test run after the bump — 289 passing
- [x] Pinned every direct dependency to a `>=` floor at the resolved version; `uv.lock` holds the
  exact set. Floors declare intent without blocking patch/minor upgrades.

### Resolved: the three LLM SDK major bumps

Re-resolving crossed a major version on all three SDKs:

| package | was | now |
|---|---|---|
| `anthropic` | 0.77.1 | **1.0.0** |
| `openai` | 2.16.0 | **3.3.1** |
| `google-genai` | 1.62.0 | **2.19.0** |

`tests/test_llm_client.py` mocks all three, so the green suite says nothing about whether the real
calls still work. Audit `backend/llm_client.py` against each SDK's current API and migration notes
before trusting a live run. Floors are `>=` so a rollback is just a `<` bound plus `uv lock`.

**Resolved by section 6.** All three direct SDK dependencies were dropped when `llm_client.py`
moved to LangChain. `langchain-anthropic`, `langchain-openai` and `langchain-google-genai` pin the
SDK versions they are tested against, so the unverified bumps are no longer ours to audit. No live
run is blocked on this.

---

## 5. Tooling alignment with `~/cortexhb/core`

**Status:** done

Brought the mature project's standards over, adapted to this repo (GitHub not GitLab, `backend/`
not `src/core/`).

- [x] `[tool.ruff]` — line-length 100, `E,F,W,I,UP,B,C4,SIM,RUF`, google docstrings
- [x] `[tool.pyrefly]`, `[tool.pyright]`, `[tool.coverage]`, `[tool.pytest.ini_options]`
- [x] `CLAUDE.md` rewritten from the cortexhb guidelines, keeping MediaSage specifics
- [x] Whole repo brought to lint-clean (94 violations fixed)

---

## 6. Architectural refactor

**Status:** in progress — `config` done, other modules pending

Method: take one large module, extract its data into Pydantic `BaseModel`s first, then group the
business logic into sensible modules. Repeat. Tests mirror the source tree exactly.

### Done: `backend/config.py` to `backend/config/`

| file | concern |
|---|---|
| `models.py` | Pure frozen section models, plus `ConfigUpdate`, which owns the API-field to config-key mapping |
| `settings.py` | `MediasageConfig(BaseSettings)` and its source chain |
| `store.py` | `ConfigStore(BaseModel)` — the loaded instance, plus persistence of UI edits |

Loading now runs on `pydantic-settings`. YAML is the ground source
(`YamlConfigSettingsSource` over `[config.yaml, data/config.user.yaml]` with `deep_merge=True`) and
every setting is reachable from the environment under one prefix, `MEDIASAGE_<SECTION>__<FIELD>`.
That replaced the hand-rolled merge and precedence helpers and the fourteen `env_or_yaml` calls
outright — no custom sources, no per-field environment name table.

Removed as floating functions, now methods on `ConfigStore`: `deep_merge`, `read_yaml`,
`load_yaml_config`, `get_env_or_yaml`, `remove_empty_values`, `save_user_config`, `get_config`,
`refresh_config`, `update_config_values`. `UpdateConfigRequest` is an alias of `ConfigUpdate`.

Tests moved to `tests/config/{test_models,test_settings,test_store}.py`, mirroring the package.

### Decisions to revisit

Everything below was decided during the config restructure and is worth a second look.

| # | Decision | Why it may need revisiting |
|---|---|---|
| 1 | **Environment variables renamed to `MEDIASAGE_<SECTION>__<FIELD>`.** `PLEX_URL`, `ANTHROPIC_API_KEY`, `OLLAMA_URL`, `CUSTOM_LLM_URL` and the rest no longer work. | Breaking for any existing deployment. `.env`, `.env.example` and `docker-compose.yml` were migrated; `.env.bak` and `data/config.user.yaml.bak` hold the originals. |
| 2 | **Provider auto-detection removed.** There is one `api_key` field, so "whichever provider's key is set wins" is no longer expressible. | Was a real convenience for cloud users. Moot if section 7 lands. |
| 3 | **No defaults for anything LLM-related.** `ProviderSpec` and its `MODEL_DEFAULTS` table are deleted; provider is required, and local providers must state `endpoint_url` and `context_window`. | A default model name goes stale and then quietly sends requests to a model nobody chose. It is documentation now, in README.md. |
| 4 | **A missing or incomplete LLM section fails at startup.** `MediasageConfig.llm` has no default, so the app refuses to boot rather than breaking mid-request. | Breaks the setup wizard on a fresh install: there is no config to boot from. **Accepted, deferred** — the UI is being left broken until the frontend pass. Failing loudly at boot is preferred to failing silently mid-task. |
| 5 | **`LLMConfig` split into `CloudLLMConfig` and `LocalLLMConfig`**, a discriminated union on `provider`. `is_local` is a `ClassVar`, and `endpoint_url` / `context_window` exist only on the local class. | Call sites that read those fields now need an `isinstance` check; `_configured_endpoint_url()` in `main.py` is the one place that does. |
| 6 | **The env-switch model rule was dropped.** Setting the provider from the environment no longer discards model names the YAML recorded for the previous provider. | A stale `model_analysis` can reach a provider that does not serve it. Switching provider *through the UI* does clear them. |
| 7 | **`ollama_*` / `custom_*` collapsed into `endpoint_url` and `context_window`**, end to end: config, `ConfigResponse`, `ValidateAIRequest`, and the frontend. | The UI now infers which box to fill from `llm_provider`. Worth checking against the real UI once it runs. |
| 8 | **`.env` is now read by pydantic-settings** rather than by nothing at all — no code ever called `load_dotenv()`, despite `CLAUDE.md` claiming it. Tests disable it via an autouse fixture. | New behaviour, not a restoration. A stray `.env` on a server now takes effect. |
| 9 | **`ConfigStore.refresh()` is unused.** Kept as part of the store's role. | Dead code until something calls it. |
| 10 | **`backend/models.py` no longer suppresses its re-export lint.** The `# noqa: E402, F401` came off at the owner's instruction. | `uv run ruff check .` reports 8 errors there. Deliberate; to be addressed when `backend/models.py` is restructured. |

### TODOs cleared in `backend/config/`

Directions carried out, and so deleted from the source:

- double config shenanigans — `ollama_*` / `custom_*` collapsed to `endpoint_url` / `context_window`
- everything must be typed with proper models — the parallel tables became `ProviderSpec`, which was
  then deleted outright once the defaults themselves went
- the provider-specific logic can be abstracted — `resolve_api_key` and its branches are gone; there
  is one `api_key` field
- is `settings_customise_sources` necessary — yes, pydantic-settings ignores `yaml_file` without it
- the `ollama` `ProviderSpec` entry should go — the whole spec went with it
- local and non-local should be `LLMConfig` subclasses — now `CloudLLMConfig` / `LocalLLMConfig`

No TODOs remain in `backend/config/`.

### Done: `backend/llm_client.py` to `backend/llm/`

714 lines holding five unrelated concerns, replaced by a package. LangChain's `init_chat_model`
covers all five providers behind one signature, so the transport block and its per-provider
branching went entirely.

| File | Holds |
|---|---|
| `models.py` | `LLMResponse` (pydantic, built from `AIMessage`), `TokenBudget`, the `Ollama*` admin models |
| `client.py` | `LLMClient` over LangChain, plus `LLMClientStore` replacing the module global |
| `json_parse.py` | Fence stripping, smart quotes, bracket scanning, `json_repair` fallback |
| `ollama.py` | `OllamaClient` on the official `ollama` SDK, for `/api/tags` and `/api/show` |
| `constants.py` | Fixed literals only; anything that varies by machine is config |

Dependencies swapped: `anthropic`, `openai` and `google-genai` out; `langchain` 1.3.16 with the
anthropic / openai / google-genai / ollama integrations in, plus `ollama` declared directly.

**What went away:** `MODEL_COSTS`, `MODEL_CONTEXT_LIMITS`, `estimate_cost_for_model`,
`get_model_cost`, `get_model_context_limit`, `get_max_tracks_for_model`, `get_max_albums_for_model`,
`get_llm_client`, `init_llm_client`, the `_llm_client` global, `_complete_anthropic`,
`_complete_openai`, `_complete_gemini`, `_complete_ollama`, the `_complete` dispatch, the
hand-rolled Gemini retry loop, and the three raw-SDK probes in `/api/setup/validate-ai`.

### Decisions from the LLM restructure

| # | Decision | Why it may need revisiting |
|---|---|---|
| 11 | **LangChain is now the transport for every provider**, chosen over section 7's cut-to-OpenAI-compatible. It handles responses/completions and the Anthropic surface uniformly, and the rest of `cortexhb/` already uses it. | Section 7 is largely moot: there is no per-provider branching left to delete, only the name map in `constants.py`. |
| 12 | **`context_window` is required of every provider**, not just local ones. `MODEL_CONTEXT_LIMITS` and its `128_000` fallback are gone. | Every existing deployment must set it. A per-model table goes stale; a guessed window overflows the model silently. |
| 13 | **Prices are config, split by role.** `cost_analysis_input/output` and `cost_generation_input/output`, defaulting to `0.0` meaning unpriced. `is_priced` tells the UI whether to show a figure. | A single price pair was the original sketch; it breaks two-model setups where analysis and generation cost differently. Four flat fields keep `FIELD_MAP` flat. |
| 14 | **Timeout, output cap, retries and probe timeout moved to `LLMConfig`**; per-item token figures and budgeting fractions to a new `budget` section. | Anything that varies machine to machine is the user's to tune, not a constant. `constants.py` keeps only structural literals. |
| 15 | **The token-budget floor is gone.** `max(100, ...)` returned 100 tracks for a 512-token window, roughly 4000 tokens into a window that could not hold them. Now returns 0. | Callers that treated 0 as "no limit" need checking; `main.py` was updated. |
| 16 | **Ollama admin runs on the official `ollama` SDK** rather than hand-rolled `httpx`. `context_window` is `int \| None`; `context_detected` is gone, since a null window says the same thing without a 32768 stand-in. | The SDK is a transitive dependency of `langchain-ollama`, now declared directly. |
| 17 | **`/api/setup/validate-ai` probes with one real completion** through the same path the app uses, so `ValidateAIRequest` now needs `model` and `context_window`. | The wizard does not send them yet. Still broken by design, per decision 4. |
| 18 | **Errors from Ollama stay data, not exceptions.** `list_models` / `status` return a model carrying `error`. | Deliberate exception to failing loudly: the caller is a settings page probing a URL the user may have typed wrong. |

### TODOs cleared in `backend/llm/`

- drop `MODEL_COSTS`, stale by nature — deleted; prices are config
- `MODEL_CONTEXT_LIMITS` should be user tunable — deleted; `context_window` is required config
- a `constants.py` per module, no magic numbers — done, and the tunables went further, into config
- `LLMResponse` is exactly why I want langchain — now a pydantic model built from `AIMessage`
- these estimations are never right — post-call figures are the provider's own `usage_metadata`
- langchain (on `LLMClient`) — done
- encode ollama calls into an ollama client — `OllamaClient` on the official SDK

Left in place, unresolved: `# TODO: Convert to structured responses later` in `json_parse.py`.
`with_structured_output` would replace the whole module, but it needs a schema per call site,
which means touching `analyzer.py`, `generator.py` and `recommender.py`.

### Bugs found and fixed in `llm_client.py`

- **Smart-quote normalisation was dead code.** One line replaced a straight double quote with an
  identical straight double quote, a no-op. The next line was worse: its three consecutive single
  quotes opened a triple-quoted string, so it parsed as a *single* two-argument call replacing the
  literal text `, "').replace(` with an apostrophe. The curly quotes it was written with had been
  flattened at some point. Confirmed by AST dump; now a `str.maketrans` table using `\uXXXX`
  escapes so it cannot happen again.
- **`json_repair` never raises**, so the "all strategies failed" branch was unreachable: prose came
  back as an empty string and was returned as a successful parse. Empty results are now a failure.
- **Three of five providers had no timeout** — Anthropic, OpenAI and Gemini all called without one,
  against the project's own rule. LangChain now takes it from config for every provider.
- **`max(100, ...)` overflowed small windows** — see decision 15.
- **`LLMClient.__init__` was typed `LLMConfig`** but read `config.provider` and
  `config.endpoint_url`, neither of which exists on that base. Now typed `LLMSection`.
- **`LLMResponse.content` was declared `str`** but OpenAI returns `str | None`; a dataclass
  validated nothing, so `None` reached `.strip()`. Pydantic now rejects it.

### Done: `backend/library_cache.py` to `backend/db/`, `backend/library/`, `backend/results/`

**Status:** complete. 1149 lines became 1463 across three packages; `library_cache.py` deleted.

1149 lines holding four datasets that share nothing but a database file.

| Lines | Concern | Moves to |
|---|---|---|
| 23–57 | Six module globals, three mutable | `db/engine.py` (engine replaces them) |
| 60–121 | Thread-local connections, WAL pragmas | `db/engine.py` |
| 123–320 | Schema DDL, hand-rolled migrations, genre backfill | `library/tables.py` + Alembic |
| 322–386 | SQL predicate builder (string concatenation) | `library/filters.py` |
| 388–597 | Track reads, staleness, checkpoints | `library/tracks.py`, `library/sync.py` |
| 598–763 | `sync_library`, 165 lines in one function | `library/sync.py` |
| 829–1003 | Album aggregation, play-history familiarity | `library/albums.py` |
| 1005–1149 | Results CRUD | `results/` — independent, zero joins to tracks |

Albums are not a fifth dataset: they are a `GROUP BY parent_rating_key` over tracks and stay a
query, not a table.

Public surface actually consumed elsewhere is 15 functions plus `DATA_DIR`. `ensure_db_initialized`
returns a raw connection to `main.py`, so the module's internals are currently its interface.

### Decisions for the data layer

| # | Decision | Why it may need revisiting |
|---|---|---|
| 19 | **SQLModel as the ORM**, over SQLAlchemy Core. Chosen for the cortex standard and one class per table. | The identity map is overhead on a 50k-row bulk sync, so the sync path uses a Core `on_conflict_do_update` statement through the session rather than `session.add()`. Not a workaround: SQLModel sits on SQLAlchemy and Core is the supported escape hatch. |
| 20 | **Postgres portability is a hard requirement** (cortex standard). Nothing above `backend/db/` names a dialect. | Costs the SQLite-only tricks listed below. Only `db/engine.py` and `db/statements.py` know a dialect name. |
| 21 | **The three `track_genres` triggers are deleted.** They used `json_each`, which is SQLite-only. `track_genres` is now written by the sync in the same transaction as the track rows. | The triggers existed so that *no writer* could desync the two tables. That guarantee now lives in code with a single write path, which is weaker by construction — it needs a test that asserts it directly. |
| 22 | **`updated_at` renamed to `sync_token`.** The column was declared `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` but held an 8-byte hex sync token, swept with `DELETE FROM tracks WHERE updated_at IS NOT ?`. | A rename against a live database, so an Alembic migration rather than a `create_all`. There is still no real last-updated timestamp anywhere; adding one is a separate decision. |
| 23 | **Alembic owns the schema.** `create_all` is used in tests only. | Was not part of the option chosen — it came bundled with the SQLAlchemy Core option. Added anyway: `try: ALTER … except OperationalError: pass` has no schema version and does not survive a Postgres move. Reversible if unwanted. |
| 24 | **`results` gets its own package, same database file.** Different lifecycle, different consumers, no joins. | Shares only the engine and the migration chain. A separate file was considered and rejected: two migration chains for one deployment. |
| 25 | **`WITHOUT ROWID` dropped** from `track_genres`. | A SQLite storage optimisation with no Postgres equivalent; not semantics. Measure if the genre index regresses. |
| 26 | **`TrackFilter` replaces the parallel `(list[str], list[Any])` return.** Predicates are SQLAlchemy expressions, so conditions and parameters can no longer drift apart, and the f-string-built SQL is gone. | `_genre_exists_clause` interpolated a table alias straight into SQL. Not injectable — both callers passed literals — but one careless caller from being so. |
| 27 | **Booleans compared with `.is_(False)`, not `== False`.** | Renders `IS 0` on SQLite and `IS false` on Postgres; `== False` needs a `# noqa: E712`, which is not allowed here. Verified against both dialects. |

### SQLite-specific behaviour and its portable form

| Today | Portable form |
|---|---|
| 3 triggers using `json_each` | Application-maintained `track_genres` (decision 21) |
| `INSERT OR REPLACE` | `insert(...).on_conflict_do_update(...)`, dispatched on dialect in `db/statements.py` |
| `PRAGMA journal_mode=WAL`, `busy_timeout`, `foreign_keys` | Connect-event listener guarded on the DBAPI module; a no-op on Postgres |
| `WITHOUT ROWID` | Dropped |
| `updated_at IS NOT ?` | `sync_token` compared explicitly, with NULL handled |
| `genres TEXT` holding `json.dumps` | `sa.JSON` column: TEXT on SQLite, JSON on Postgres |
| Thread-local `sqlite3` connections | SQLAlchemy engine and pool; drops four module globals |
| `DEFAULT CURRENT_TIMESTAMP` | Python-side `datetime.now(UTC)` |

### Models discovered

Table models:

- `Track` — `tracks`. `genres` as JSON, `sync_token` replacing `updated_at`.
- `TrackGenre` — `track_genres`, `(rating_key, genre_lower)` primary key.
- `SyncState` — `sync_state`, single row held by a CHECK constraint.
- `Result` — `results`, with `snapshot` as JSON.

Data models, every one of which is a bare `dict[str, Any]` today:

- `TrackFilter`, `DecadeRange` — filtering, replacing the parallel lists and an inline `try/except int()`
- `Album` — the aggregation result
- `AlbumFamiliarity` — `level: Literal["unplayed","light","well-loved"]`, `last_viewed_at`; currently `dict[str, dict]` whose shape lives only in a docstring
- `SyncOutcome`, `SyncCheckpoint`, `SyncSnapshot` — return values and the mutable module global
- `ResultSummary`, `ResultRecord` — the list row and the full record

Reused rather than duplicated: `GenreCount`, `DecadeCount` and `SyncProgress` already exist in
`backend/models.py`. The API `Track` there stays separate from the table `Track` — different shapes
(`art_url`, `genres` as a list), which is the SQLModel base/table/public split.

### Defects found in `library_cache.py`

Not yet fixed; each is addressed by the plan above.

1. **`updated_at` holds a hex token, not a timestamp** — see decision 22.
2. **Migrations are `try: ALTER … except OperationalError: pass`**, six of them. That swallows every
   operational error, not just "duplicate column": a locked database or a typo'd DDL both read as
   "already applied". No schema version exists.
3. **`except Exception` spans the whole 150-line body of `sync_library`**, returning
   `{"success": False}`. A bug in the batch tuple and a Plex timeout are indistinguishable.
4. **Query structure is built by f-string.** Values are parameterised; the SQL around them is not.
5. **Conditions and parameters travel as parallel lists.** `get_album_candidates` calls the builder
   twice and concatenates both halves; correctness depends on both being extended in the same order.
6. **Every read returns `dict[str, Any]`** — fifteen functions, no typed row, against the project's
   own rule about structured data crossing a module boundary.
7. **Three mutable module globals** plus two locks and a path set. Tests monkeypatch four of them
   (`tests/test_library_cache.py:16-19, 481`) to get isolation; the fixture compensates for the design.
8. **`ensure_db_initialized()` hands a live connection to `main.py`.**

### What was written

`backend/db/` — engine, sessions, and the one dialect-aware statement.

- `engine.py` — `Database` holding the engine, `db.session()` / `db.connection()`, dialect-guarded
  pragmas, `configure()` for tests. Sessions do not expire instances on commit, so a returned row
  stays readable after the block.
- `statements.py` — `upsert()`, dispatched across the sqlite and postgresql dialects.
- `migrate.py` — `upgrade_to_head()`, called once from the lifespan. Builds its Alembic config in
  memory so no file has to sit beside the package.

`backend/library/` — the mirror of the Plex library.

- `tables.py` — `Track`, `TrackGenre` (cascading FK), `SyncState`, `genre_rows()`.
- `filters.py` — `TrackFilter`, `DecadeRange`, verified against both dialects.
- `live.py` — `LiveVersionRule`, compiled once per sync rather than per track.
- `tracks.py` — `all_tracks`, `filtered`, `count`, `genre_decade_stats`.
- `albums.py` — `candidates`, `familiarity`.
- `sync.py` — `LibrarySync` plus `sync_status`, `has_tracks`, `is_stale`, `server_changed`,
  `clear_cache`. The only writer of both tables.
- `models.py`, `constants.py` — domain models and the two structural literals left.

`backend/results/` — `tables.py`, `models.py`, `store.py` (`save`/`get`/`page`/`remove`).

`backend/migrations/` — `0001_orm_schema`, one revision covering a fresh database and a
pre-Alembic one without a stamping step. Both paths verified against the models with
`compare_metadata`; the diff is empty for each.

Dependencies added: `sqlmodel` 0.0.39, `sqlalchemy` 2.0.52, `alembic` 1.19.1.

### Models moved out of `backend/models.py`

`AlbumCandidate`, `GenreCount`, `DecadeCount`, `SyncProgress` to `backend/library/models.py`;
`ResultListItem`, `ResultListResponse`, `ResultDetail` to `backend/results/models.py`. Every
importer repointed; no aliases. `LibraryStatsResponse`, `LibraryCacheStatusResponse` and
`SyncTriggerResponse` stay as HTTP envelopes.

### `LibraryConfig`, the new tunables section

`sync_batch_size`, `stale_after_hours`, `well_loved_avg_plays`, `live_keywords`,
`dated_titles_are_live`. Env/YAML only, like `BudgetConfig`. Documented in `.env.example` and
`CLAUDE.md`.

### Behaviour changes from the data-layer rewrite

- The track upsert, its genre rows, and the resume checkpoint now commit in one transaction. The
  old code committed the batch and the checkpoint separately, so a crash between them checkpointed
  progress the rows had not made.
- `count()` no longer returns `-1` for an empty cache. Both callers guarded with
  `has_cached_tracks()` first, so the sentinel was dead.
- `needs_resync` is gone. It only tracked the ad-hoc `ALTER TABLE` migrations Alembic replaces. A
  migration that invalidates cached data clears `sync_state` instead. `LibraryCacheStatusResponse`
  lost the field; `frontend/app.js:2341` still reads it and now sees undefined.
- `results.created_at` is a real `datetime`, not SQLite's `CURRENT_TIMESTAMP` string, so the wire
  format is ISO 8601 rather than `"2026-08-21 12:00:00"`.
- Album genres dedupe case-insensitively. An album with `["Rock", "rock"]` used to display both.
- The history indexes lost their `DESC`. An expression index defeats autogenerate, which reported
  them as changed on every run; both backends scan an index backwards anyway.
- The recommendation preview lost an unreachable branch: the outer check already proved the cache
  was populated, so "No albums match your filters" could never be sent. Filtering to zero albums
  still reports "needs a fresh sync", which is the wrong message and predates this work.

### Done: `backend/recommender.py` to `backend/recommender/`

**Status:** complete. 1100 lines became 1500 across eleven modules; `recommender.py` deleted.

| Concern | Moves to |
|---|---|
| Every prompt string (~55% of the file) | `prompts.py` |
| The twelve taste dimensions | `dimensions.py` |
| Session dict, its lock, expiry and eviction | `sessions.py` |
| Cost logging and JSON decoding, repeated per call | `calls.py` (`MeteredClient`) |
| Two duplicated fuzzy-match cascades | `matching.py` (`AlbumMatcher`, two configs) |
| Gap analysis, filters, questions, selection | `selection.py` |
| Fact extraction, discovery validation | `facts.py` |
| Pitch writing, validation, rewrite | `pitches.py` |
| The one-round orchestration lifted out of `main.py` | `round.py` |
| The facade and its rebuild-on-client-change | `pipeline.py` |

Album identity became `AlbumRef` rather than a `"artist|||album"` string, so no stage parses a key
back apart. `format_answers_*` became `AnswerSet.for_selection`/`for_pitch`; `build_taste_profile`
became `TasteProfile.of`.

### Defects found in `recommender.py`

- `familiarity_data[key]["level"]` in both `select_albums` and `write_pitches`.
  `albums.familiarity()` returns `dict[str, AlbumFamiliarity]`, so any `familiarity_pref != "any"`
  raised `TypeError: 'AlbumFamiliarity' object is not subscriptable` and aborted generation.
- `RecommendationPipeline.sessions` defaulted to a shared `SessionStore()` instance. Pydantic
  deep-copies a model default and `SessionStore` holds a `threading.Lock`, so **every**
  construction raised `TypeError: cannot pickle '_thread.lock' object`. Now a `default_factory`.
- `dimensions.fill` deduped against the catalogue but not against the model's own answer, so
  `["era", "era"]` asked the same question twice.
- `SessionStore.create` swept before inserting, so the store could hold `MAX_SESSIONS + 1`.

### Done: `backend/main.py` to `backend/api/`

**Status:** complete. 1604 lines became 14 plus a package; largest module is 328.

| Lines | Concern | Moves to |
|---|---|---|
| 106–241 | Lifespan, provider labels, config response builder | `api/app.py`, `routes/setup.py`, `routes/config.py` |
| 166–172 | `_is_llm_configured` and 15 hand-written 503 checks | `api/guards.py`, as FastAPI dependencies |
| 619–702 | Two blocks of hardcoded token-cost arithmetic | `api/estimates.py`, each constant named |
| 703–755, 1049–1424 | Two hand-rolled SSE frame formats | `api/sse.py` |
| 846–876 | Two lazily-built shared clients, two locks | `api/clients.py` |
| 116–125 | The background task set | `api/background.py` |
| 1049–1424 | One 375-line recommendation handler | `recommender/round.py` |
| the rest | 35 routes | `api/routes/`, one module per resource |

Shape follows `~/Cortexhb/core`: a `create_app()` factory mounting `register_<x>_routes(app)` from
one module per resource, private handlers, and a module map in every package `__init__`.

Every store is now reached through `api/guards.py` and nowhere else, so one patch target covers
every caller — which is also what made the route tests small.

Both `pyrefly` bugs named below are gone by construction: the session in `/api/recommend/questions`
is created before the `try` rather than probed with `'session_id' in locals()`, and
`_load_candidates` returns a list or raises, so nothing passes `None` where a list is required.
`backend/api/`, `backend/plex/` and `backend/recommender/` now report zero `pyrefly` errors.

### Done: `backend/music_research.py` to `backend/research/`

**Status:** complete. 629 lines became eight modules, largest 145.

| Concern | Moves to |
|---|---|
| Bare `dict` payloads with `.get()` chains at every read site | `research/models.py`, one parser per shape |
| The shared client and the MusicBrainz rate limit | `research/http.py` — `SharedHttp`, `Throttle` |
| SSRF checks and manual redirect following | `research/safety.py` |
| Three search strategies and two lookups | `research/musicbrainz.py` |
| Article fetch plus the section filter | `research/wikipedia.py` |
| Front cover, release then release group | `research/covers.py` |
| Review fetch and readability extraction | `research/reviews.py` |
| The pipeline over all four | `research/album.py` — `AlbumResearch` |

Renamed with no shim: `MusicResearchClient` to `AlbumResearch`, `research_album()` to `of_album()`,
`fetch_cover_art()` to `cover_art()`. `tests/research/` covers all eight modules, including the
five cases the deleted `tests/test_music_research.py` held.

### Done: module constants to configuration

**Status:** complete. Four new sections plus four fields on `PlexConfig`.

| Section | Was | Now |
|---|---|---|
| `MEDIASAGE_PLEX__` | `PAGE_SIZE`, `RETRY_BACKOFF`, `RECONNECT_COOLDOWN`, `CONNECT_TIMEOUT` | four fields on `PlexConfig` |
| `MEDIASAGE_MATCHING__` | `matching.FUZZ_THRESHOLD`, `SELECTION_MATCHER`, `PITCH_MATCHER` | `MatchingConfig`, five floors |
| `MEDIASAGE_RECOMMEND__` | nine constants across `sessions`, `selection`, `dimensions` | `RecommendConfig` |
| `MEDIASAGE_RESEARCH__` | eleven constants across five research modules | `ResearchConfig` |
| `MEDIASAGE_ART__` | `ART_TIMEOUT`, both cache headers, the allowlist, the hop limit | `ArtConfig` |

Two module singletons became functions, so a config change is picked up rather than frozen at
import: `SELECTION_MATCHER`/`PITCH_MATCHER` are now `selection_matcher()`/`pitch_matcher()`.
The research sources take their `ResearchConfig` by constructor instead of reading a global, which
is what made them testable without patching module state.

What deliberately stayed a module constant: prompt text and the token estimates measured from it
(`api/estimates.py` — they move with a prompt rewrite, not with a deployment), protocol shapes and
regexes, and the release-group scoring weights. `api/estimates.py` had its own
`PLAYLIST_TOKENS_PER_TRACK` duplicating `budget.tokens_per_track`; it now reads the config field.

### Done: one id format

Every generated id is `str(uuid.uuid4())`. Three widths went with it — `ID_LENGTH = 12` truncating
a uuid4 in `recommender/sessions.py`, `ID_BYTES = 8` in `results/store.py`, `TOKEN_BYTES = 8` in
`library/sync.py` — along with `RESULT_ID`, a regex that claimed to be the shape the store mints
and accepted `{8,16}` while the store only ever wrote 16. `routes/results.py` now validates by
parsing, round-tripped through `str` so braces and `urn:` forms are still refused.

`0002_uuid_result_ids` reissues existing `results.id` values: the route rejects the old hex ids, so
without it a saved result would list and then 400 when opened. Idempotent, and nothing references
the column. `api/routes/art.py`'s ETag is untouched — an md5 of the thumb path, not an id.

A root `installed_config` autouse fixture installs a complete configuration for every test, since
tunables are now read at call time; `tests/config/` opts out so it can still assert on loading.

### Done: stages as classes, helpers on their owners

`selection.py`, `pitches.py` and `facts.py` took `call: MeteredClient` as the first argument of
every public function — a class wearing a module. Each is now a class over `Stage`, a one-field
base in `calls.py` holding the client the stage spends through. `RecommendationPipeline` builds
them per session (`_selection`, `_facts`, `_pitches`), so nothing else changed at the call sites.

`Pitches.validate` is named `fact_check`: pydantic's `BaseModel` carries a deprecated `validate`
classmethod, and shadowing it is a `bad-override` under pyrefly even though it runs.

The pure helpers moved onto the classes that used them: `plain_text` (static) and `trimmed` onto
`Reviews`, `useful_sections`/`_capped`/`_title_of` onto `Wikipedia`. `trimmed` and
`useful_sections` read their caps off `self.config` instead of taking them per call.

`CoverArt._front_of` is gone: `front` walks the two endpoints itself, so the wrapper that called
the same helper twice no longer exists.

Deliberately left as module-level: `prompts.py` (text builders with no state), `dimensions.py` (a
fixed catalogue), the `settings()` config accessors (the project-wide read-at-call-time idiom),
`as_list`/`as_dict` in `calls.py`, and `safety.py`'s `is_safe`/`fetch_safely` — security policy
with no owner, called with a client that belongs to someone else.

### Done: `analyzer.py` as a class

`Analyzer` holds the two clients its calls read, injected rather than fetched. `analyze_prompt` and
`analyze_track` are methods; the two prompt-building f-strings are staticmethods beside them.

The route's `plex` and `llm` parameters were declared for the guards alone while the analyzer read
both stores itself. They are now passed in, which deletes both the apology in the route docstring
and the `RuntimeError("Plex client not initialized")` branch -- unreachable behind `guards.Plex`,
and a 500 where the guard already answers 503.

`backend/analyzer.py` became `backend/analyzer/`, which settles its TODO: the two system prompts
and the two builders are in `prompts.py`, `Analyzer` is in `analysis.py`. `from backend.analyzer
import Analyzer` still resolves, so the route did not change.

`prompts.GENRE_LIMIT = 30` names what was a bare `[:30]`. Left a module constant rather than a
config field: it is a property of the prompt, not of a deployment. Worth revisiting if a library
with hundreds of tags reports bad suggestions.

`tests/test_analyzer.py` rewritten and split to mirror -- 6 tests that mocked two stores became 22
across `tests/analyzer/test_analysis.py` and `test_prompts.py`.

### Done: the TODOs left in the tree

- **`generator.py` prompts.** Became `backend/generator/`, mirroring the analyzer: `prompts.py`
  holds both system prompts plus `selection()` and `narrative()`, `playlists.py` holds the rest.
  `NARRATIVE_TRACK_LIMIT` names what was a bare `[:15]`.
- **`llm/client.py`, "half of this is model, half is business logic".** Split. `chat.ChatModels`
  owns configuration to chat model -- names per role, the kwargs every integration takes, the cache.
  `client.LLMClient` owns the completion. `LLMError` moved to `errors.py`, which both raise.
  `LLMClient.parse_json_response` was a third thing that belonged to neither; it is now
  `LLMResponse.parsed()`, on the object that holds the content. Named `parsed`, not `json`, because
  pydantic's deprecated `BaseModel.json` makes that a `bad-override`.
- **`test_album.py`, "why are tests for cover art using research???".** Because `AlbumResearch`
  had a `cover_art` passthrough that composed nothing. Deleted; `round.py` asks `.covers.front`
  directly, and the tests in `tests/research/test_covers.py` are the only ones left.
- **`matching.py`, "belongs in playlists" / "utils.py".** Module gone. `threshold` and
  `artist_variants` are in `generator/playlists.py` beside `_tracks_match`, their only caller;
  `simplify` is in the new `backend/utils.py`.
- **`research/safety.py`, "generic, utils.py".** `is_safe` and `fetch_safely` are in
  `backend/utils.py`; nothing about them was research-specific.
- **`results/store.py`, "none of these should be floating".** Four module functions became
  `ResultStore`, reached as `results_store` like every other store. A plain class, not a model: it
  carries no fields. Tests could not patch methods on a pydantic instance either.
- **`llm/chat.py` type error.** `init_chat_model` widens to `BaseChatModel | _ConfigurableModel`
  under the general overload. Narrowed with an `isinstance` guard that raises `LLMError`, so a
  LangChain change is loud rather than an `invoke` on the wrong object.

Scripted-LLM fixtures now set response *content* and let the real parser decode it, so a stage is
tested against what a model actually sends rather than against a mocked parse.

Still open: `json_parse.py` "Convert to structured responses later", and three new ones in
`backend/api/` -- `guards.py` on floating functions and singletons, `estimates.py` on floating
functions, `clients.py` on being ugly.

### Remaining modules

All five originals are done. What is left, by size: `models.py` (494), `generator.py` (455).

Wanted, unchanged:

- Proper class-based design
- Clear seams and separation of concerns
- SOLID
- DRY
- Pydantic models wherever they fit

To decide during planning: module/package layout, where the seams go, dependency-injection approach for FastAPI, and how far to take the split without churning the whole codebase at once.

### Known issues to fix during the refactor

- `uv run pyrefly check` reports 52 errors. Deliberately deferred. Genuine bugs among them:
  - `backend/plex_client.py:588` — `filters` may be used uninitialized
  - `backend/plex_client.py:1258` — `tracks_queued` may be used uninitialized
  - `backend/main.py:1106` — `session_id` uninitialized, guarded by an `'x' in locals()` hack
  - `backend/main.py:1256,1286` — `None` passed where a list is required
  - `backend/recommender.py:312,314` — plain `str` assigned to `Literal[...]` fields
  - The rest are the `self._server`/`self._library` Optional pattern in `plex_client.py`, which the
    class-based redesign should replace with a non-optional connection object.

### Bugs found and fixed along the way

- `needs_resync()` raised `NameError` — `_migration_applied` was declared `global` but never
  defined at module level (introduced during the sync rewrite; regression test added).
- `CREATE TABLE tracks` omitted `view_count`/`last_viewed_at`, so the `ALTER` succeeded on every
  fresh database and flagged a migration — every new install triggered a spurious full re-sync.
  Same for `sync_state` and `results.subtitle`.
- `tests/test_config.py` asserted against the developer's `.env` (`load_dotenv()` runs at import).
  Seven hardcoded `delenv` lists replaced with a `clean_config_env` fixture.
- Two `asyncio.create_task` calls kept no reference, so a running sync could be garbage collected
  mid-flight.

### Done: nothing broken gets saved

Two ways into the same settings had drifted apart. The wizard proved a dependency before writing;
`POST /api/config` wrote whatever it was handed and rebuilt the client *after* persisting, so a
wrong token reached disk and survived a restart. And `ConfigStore.apply` published the new config
to memory before the file write that can raise `ConfigSaveError` -- a failed save left the process
running on settings that were nowhere on disk.

- **`ConfigStore` splits into `candidate` and `commit`.** `candidate(update)` computes the
  `ConfigChange` an update would produce and keeps nothing; `commit(change)` writes first, then
  publishes. `apply` is the two called together, for a caller with nothing to prove.
- **`backend/api/probes.py`** holds `PlexProbe` and `LLMProbe`, both `.of(...)` over a candidate
  section, neither raising: every way a dependency can refuse is an answer a form has to show.
  `rejected(update, config)` is the gate both routes call.
- **What is probed is gated on `ConfigUpdate.reconnects(section)`**, not `touches`. `CONNECTING`
  names the fields that decide whether a dependency answers at all; editing a price is a number the
  UI reports back, and must not spend a completion nor fail because a provider is down.
- **Both routes probe the *merged candidate*, not the form.** A wizard field is one part of a
  section; the deployment's own tuning still applies to the connection being tested.

`PROVIDER_LABELS` and the SDK-error-to-form-error mapping moved to `probes.py` with the probing
they belong to.

### Done: the nullables that were never nullable

Three different things were wearing `X | None`, and only one of them meant anything.

**"None means use the default."** A parameter typed nullable so the body could do `x or config.x`.
Nobody ever passed None on purpose -- it was the *absence* of an argument, spelled twice, and the
type said "this can be None" to every reader and every checker forever. Gone:

- `AlbumResearch.__init__` takes its `http` and `config`; `AlbumResearch.configured()` is the
  constructor that reads the store, the same shape as `PlexClient.of` and `LLMClient.of`.
- `iter_raw_tracks(page_size)`, `is_stale(max_age_hours)` and `dimensions.fill(count)` are gone
  outright -- no production caller passed any of them. Two existed only so one test could avoid
  patching the configuration it was actually testing.
- `max_exclusion_albums` is an `int` end to end; 0 takes the configured cap, which is what the
  route was already spelling as `request.max_albums or None`.
- `ollama_client(url)` and `ResultStore.page(result_type)` take `""`, which already meant
  "everything" in both.

**"This collection might be missing."** `list[X] | None = None` then `x or []`, everywhere, because
ruff's B006 refuses a mutable default. B006 does *not* fire when the annotation is read-only, which
is what these parameters always were: `Mapping[str, X] = {}` and `Sequence[X] = ()` are accepted,
honest about not mutating, and carry no null. Applied across `selection.py`, `pitches.py`,
`pipeline.py`, `round.py`, `prompts.py` and `generator/`.

**Dead state.** `RecommendSession.taste_profile` was written on every round and never read once --
three nullables and a branch for a field nothing consumed. `RoundInputs.profile` is now a
`TasteProfile`, empty in library mode, which deletes the `NO_PROFILE` guard: it could only fire if
`_load_candidates` and `is_discovery` disagreed about `request.mode`, and both read the same field.
`_familiarity()` returns `{}` rather than None -- an unknown play count and a zero one shape the
prompt identically.

What stayed is what carries information: `Track.year`, `user_rating`, Ollama's `context_window`,
every field of `ConfigUpdate` (None is "not supplied", which is the whole point of a patch model),
`seed_track`, `albums.familiarity(parent_rating_keys)` (None is every album, `[]` is none), and the
two optional callbacks.

Net: 57 nullable annotations removed from `backend/`, 6 added. Pyrefly is down from 42 errors to 36
-- the rest are SQLModel column expressions.

### Still open: the stores hand out None

`LLMClientStore.get()`, `PlexClientStore.get()` and `PipelineStore.get()` all return `X | None`, and
that None is then re-checked in `guards.py`, in every `require_*`, and again in the routes. It is a
real state -- the app boots with no Plex token -- but it should be resolved at one boundary rather
than travelling. `LLMClientStore` already has the answer next to the problem: `require()` raises,
`get()` returns the optional, and `guards.require_llm` calls `get()` and redoes the check by hand.

`SharedHttp._client`, `DbEngine._engine` and the two module globals in `api/clients.py` are a
different case: the value can always be produced, so the None is a cache detail that should never
have reached a signature. `api/clients.py` still carries its own TODO about this.

Both belong with the `guards.py` question rather than with this pass.

### Done: `guards.py` deleted

It was four jobs in one file, and only one of them needed a module: four `Annotated[..., Depends]`
aliases, four `require_*` functions that existed only to be depended on, six one-line pass-throughs
to a store, and `llm_is_configured`, which is not a guard at all. The stores were reached through it
so that one patch target covered every caller -- a test convenience holding up a production module.

- **Each package says how to get its own thing.** `connected_plex` / `held_plex` /
  `plex_is_connected` in `plex/client.py`, `configured_llm` in `llm/client.py`, `built_pipeline` /
  `available_pipeline` in `recommender/pipeline.py`, `configuration` in `config/store.py`.
  Module-level functions rather than store methods: a bound method of an unfrozen pydantic model is
  unhashable, and FastAPI hashes a dependency on every request.
- **"Not configured" is an exception, not a status code.** `PlexNotConnected` and
  `LLMNotConfigured` are raised where the state is known; `app.py` registers one handler that turns
  either into a 503. No layer in between knows both facts.
- **Routes spell out what they resolve.** `plex: Annotated[PlexClient, Depends(connected_plex)]`
  rather than `plex: guards.Plex`. Longer, and there is no module in the middle to wonder about.
- **`llm_is_configured` became `LLMSection.is_configured`**, overridden on `LocalLLMConfig`, which
  is where "a hosted provider needs a key, a local one needs a URL" belongs.
- **Tests override dependencies instead of patching a module.** `app.dependency_overrides` is what
  the mechanism is for; `serve_plex` in `tests/api/conftest.py` answers all three Plex dependencies
  from one client. `test_guards.py` is `test_unavailable.py` and now runs against the real
  dependencies over empty stores -- the state a fresh install is in.

### Done: the stores answer for themselves

The dependency functions that replaced `guards.py` were indirection of their own -- `connected_plex`
did nothing but call `plex_store.get()` and check it. They existed for one reason: a bound method of
an unfrozen pydantic model is unhashable, and FastAPI hashes every dependency on every request.

The stores were models for no benefit. `PlexClientStore`, `LLMClientStore`, `PipelineStore` and
`ConfigStore` are plain classes now, so their methods *are* the dependencies:
`Depends(plex_store.require)`, `Depends(config_store.get)`, `Depends(pipeline_store.require)`.
Six module functions deleted. `validate_assignment` went with them, which is what had been forcing
tests to patch a method rather than set a field.

`PipelineStore.get(client)` is `for_client(client)`, so `require()` and `available()` can be the
no-argument dependencies and the store reads `client_store` itself.

**`init()` is gone too.** `plex_store.init(config)` was `self.client = PlexClient.of(config)` behind
a method -- a setter that hid a constructor, on a public field the tests already assigned. The three
callers (boot, a settings save, the wizard) now write `plex_store.client = PlexClient.of(config)`.
That also moved the test seam onto `PlexClient.of`, which is what actually opens a connection.

Still module-level singletons. That part is unchanged: `app.state` would need a `Request` parameter
threaded into a function per dependency, which is the indirection this pass just deleted.

### Done: the wrappers around one attribute access

Four clusters of the same defect the stores had -- a function whose whole body is one attribute
chain, or a class that reimplements nothing.

**Eight config readers.** `library_config()`, three separate `settings()`, `configured_page_size()`,
`live_rule()`, `question_count()` and `threshold()` -- six packages, four names, one shape:
`return config_store.get().<section>`. Two of them wrapped a single scalar. `config_store.get()` was
already the late read they claimed to provide, so every call site reads the chain directly now.

Tests that patched a reader had nothing left to patch. The `tuned(section, **overrides)` fixture in
`tests/conftest.py` replaces them: it reinstalls the configuration with one section changed, which
is what those tests were always really asserting on.

**`PlexClient`, 21 one-line forwards.** Every one passed `self.connection` to a module function --
the floating functions the TODO in `plex/library.py` named. `PlexLibrary`, `PlexPlaylists` and
`PlexPlayback` now hold the connection and own those functions as methods. `PlexClient` is the
connection plus the three, built over it as `cached_property` so they are views of one handle rather
than fields a caller could point at a second server. Callers say `plex.library.filtered(...)`,
`plex.playlists.create(...)`, `plex.connection.is_connected()`.

What stayed module-level is what is pure: `to_track`, `is_live`, `is_mobile`, `_decade_label`,
`_set_description`, `_active_queue_id`. The line is whether it needs the connection, not whether it
is short.

**`RecommendationPipeline`, 9 forwards.** Each was `self._selection(session_id).x(...)` over three
private factories. `pipeline.stages(session_id)` returns the three stages bound to one
`MeteredClient`, so the session is named once instead of on every call. The no-argument default is
the unattributed run filter suggestion needs, which deletes its special case too.

**`api/clients.py` and `api/estimates.py`**, both carrying their own TODO. The four module globals
and two lock idioms are `SharedClients`, one instance named `shared`; `close()` now drops each
client after closing it rather than leaving a closed handle to be handed out. The two floating
estimate functions became `FilterPreviewResponse.of` and `AlbumPreviewResponse.of`, and both models
moved out of `backend/models.py` into `api/estimates.py` next to the prompt sizes they are measured
from.

**`library/sync.py`, eight more.** Missed on the first pass: the scan matched only bodies that were
a single `return <call>`, which selects for short rather than for floating, so it caught
`library_config()` in that file and nothing else in it.

`load_state(session)` is `SyncState.load(session)` and `row_from_plex(...)` is `TrackRow.of_plex(...)`
-- both were constructors for a model, sitting in another module. `write_batch` had one caller and is
`LibrarySync._write_batch`.

`sync_status`, `has_tracks`, `is_stale`, `server_changed` and `clear_cache` are methods on
`LibrarySync` (`sync_status` as `status`). Every one of them reads the same `sync_state` row the sync
writes, and `sync_status` already reached forward to `library_sync.snapshot()` -- a module function
calling the singleton declared below it, which the class no longer has to do.

Callers say `library.library_sync.has_tracks()`. Tests that patched the module function now patch
`LibrarySync.has_tracks` on the class: pydantic refuses `setattr` for a non-field, so the singleton
itself cannot be patched.

Left alone: `json_parse.py`'s TODO. Structured responses are a real change, not indirection.

---

## 7. Cut the cloud providers (superseded)

**Status:** superseded by the LangChain move in section 6 — see decision 11.

LangChain handles all five providers behind one signature, so there is no per-provider branching
left to delete: the whole thing is a five-line name map in `backend/llm/constants.py`. Cutting
providers would now save nothing but the four integration packages. The `anthropic`, `openai` and
`google-genai` SDK dependencies were dropped anyway, which addressed the major-version risk in
section 4 without removing any user-facing capability.

The original plan is kept below for the record.

---

Intent is local inference only, at most OpenAI-compatible endpoints. That means keeping `ollama`
(native REST via httpx) and `custom` (openai SDK against any `base_url`), and dropping `anthropic`
and `gemini`.

Scope: 27 provider branches across `backend/`, plus `config.py`, `llm_client.py`, `models.py`,
`main.py`, `frontend/app.js`, and five test files. Removing two of four providers should collapse a
fair amount of that branching rather than just deleting arms of it.

Open questions:

- Keep `ollama` and `custom` as distinct providers, or fold Ollama in via its OpenAI-compatible
  `/v1` endpoint and keep a single code path? Ollama's native `/api/generate` is currently used for
  context-window auto-detection via `/api/show`, which the OpenAI-compatible surface does not expose.
- Drop the `anthropic` and `google-genai` dependencies from `pyproject.toml` (removes ~15 transitive
  packages and the two major-version risks above).
- What to do with cost transparency (constitution principle 4) when local inference is free — the
  token counts stay meaningful, the dollar figures do not.

Worth doing **before** the section 6 refactor: no point designing clean seams around provider
abstractions that are about to be deleted.
