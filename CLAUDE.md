# MediaSage — AI Coding Assistant Guidelines

**Edit code freely; commit nothing unless asked.** Making changes is the work — proposing them and
waiting is not. What needs approval is anything that leaves the working tree: commits, branches,
pushes, PRs. Finish the edits, say what changed, and let the owner decide what lands.

## Project overview

MediaSage is a self-hosted web app that generates Plex music playlists and album recommendations
using LLMs with library awareness. It uses a filter-first approach so every suggested track is
guaranteed playable.

## Role

Write code that is correct by construction, operationally safe, and easy to reason about. Read the
existing code before touching any file.

- Prefer the simplest solution that satisfies the requirements.
- Never add complexity, abstraction, or features that were not asked for.
- When in doubt, do less and ask.

## Working with uncommitted changes

**Never discard working-tree changes you did not make.** `git checkout --`, `git restore`,
`git reset --hard`, `git stash`, and overwriting a modified file all destroy uncommitted work.

- Before running any of those on a file with unstaged changes, confirm *you* authored those exact
  changes in this session.
- If you do not recognize a change, assume the owner made it deliberately and ask before touching it.
- Never "restore to a known good state" on a hunch.

## Running the app

**Never start the app, a server, or a container.** No `docker run`, no `uvicorn` serve, no
background app processes — the owner runs it and controls what occupies his ports. Verify
statically instead: `docker build`, `uv run pytest`, `uv run ruff check .`. When runtime
confirmation is genuinely needed, say what to run and let him run it.

## Environment

Dependencies are managed with [`uv`](https://docs.astral.sh/uv/); the virtualenv is
repository-local at `.venv/`. Python 3.14.

- **Always prefer `uv`.** Run every Python command, script, and test through `uv run`
  (`uv run pytest`, `uv run ruff check .`) — never the system interpreter, never `.venv/bin/…`
  directly.
- Add dependencies with `uv add <pkg>`, then `uv lock`. Never `pip install`.
- `pyproject.toml` and `uv.lock` are the source of truth; there are no `requirements*.txt` files.

```bash
uv sync                                              # install
uv run uvicorn backend.main:app --reload --port 5765 # dev server (owner runs this)
uv run pytest                                        # tests
uv run ruff check .                                  # lint
uv run pyrefly check                                 # types
```

## Git

This repo is on **GitHub**: pull requests, `gh`, not `glab`.

- **Do not run git unless asked.** No `git add`, `git commit`, branch creation, push, or PR unless
  explicitly requested. When a task is done, summarize what changed and stop.
- **One approval covers one commit, not a session.** Being told to commit does not authorize
  committing after every later edit. Accumulate and commit once.
- **Do exactly what was named, all of it.** "Commit" means commit, stop, report. "Commit and PR"
  means stage, commit, push, and open the PR in one pass.
- **Never commit directly to `main`.** Create the branch *before* the first commit; if already on
  `main` with uncommitted work, branch first.
- **Never rewrite history that has been pushed.** No `--amend`, `rebase`, `reset` onto an earlier
  commit, or force-push. Add a new commit instead.
- **Never undo a commit unless explicitly told to in this session.**

## Comments

Comment the constraint, the quirk, the bug, the reason — never the mechanics. `i += 1  # increment
i` adds nothing.

- **One line per comment.** Two only if a second fact is undroppable. Length is itself the defect;
  accurate content does not excuse it.
- Every **module** gets a top-of-file docstring: what it does, its entry points, its constraints.
- Every **function** gets a docstring unless it is a trivial one-liner with a self-documenting name.
  Say what it does and why it exists; do not restate the signature.
- Comment **non-obvious logic**, **workarounds** (a library bug, a protocol quirk, a safety margin),
  and **every config constant and env var** — what it controls and what the default means.
- Never explain the language itself.
- **Comments are documentation, not conversation.** No "as you can see", no narrating what you just
  did. That belongs in the reply, not the file.
- "Clean up the comments" means delete words, not rephrase them.

## Type annotations

- Annotate every signature — all parameters and the return type, including `-> None`.
- Use modern built-in generics (`dict[str, Any]`, `list[str]`, `X | None`), not `typing` forms.
- Avoid `Any`. Use it only when a value genuinely has no narrower type — never to silence an error.
- **Pydantic models for every API contract** and for structured data crossing a module boundary.

## Async correctness

- The Plex and LLM clients are **synchronous**. Every call from an `async` endpoint must go through
  `asyncio.to_thread`, or it blocks the event loop for the whole process.
- Run independent operations concurrently with `asyncio.gather()`.
- **Set an explicit timeout on every outbound call.** `timeout=None` turns a slow dependency into a
  permanent hang.
- Hold a strong reference to every `asyncio.create_task` result — asyncio keeps only weak
  references, so an unreferenced task can be collected mid-flight. Use `spawn` in
  `backend/api/background.py`.
- Release resources in `try/finally`.

## Error handling

- Retry transient failures with exponential backoff, and cap the total retry budget.
- Narrow every `except` to the exception types expected. Bare `except Exception` only at top-level
  handler boundaries that log and continue.
- Chain exceptions: `raise X(...) from err`.
- **Never destroy cached state before the operation that replaces it succeeds.** A sync writes into
  the cache and sweeps stale rows only on success.

## Testing

- **Ship tests with every new feature**, under `tests/`, mirroring the `backend/` layout.
- **Ship a regression test with every bug fix** — one that fails before the fix and passes after.
- Run the suite before calling work done: `uv run pytest`.
- Mock external dependencies (Plex, LLM servers, network) to keep tests fast and deterministic.
  Async tests need no decorator — `asyncio_mode = "auto"` is set.
- Tests must not depend on the developer's environment. Config reads `MEDIASAGE_*` variables and
  the repository `.env`; the root `installed_config` fixture installs a complete configuration for
  every test, and `clean_config_env` clears the variables for tests that assert on loading.
- Use descriptive test names and parameterize over inputs rather than copy-pasting a test body.

## Project structure

Each package's `__init__.py` opens with a map of its modules. Read that before opening a file.

```text
backend/
├── main.py              # ASGI entry point: `uvicorn backend.main:app`
├── api/                 # The HTTP layer; holds no domain logic
│   ├── app.py           #   create_app(), the factory, and the lifespan
│   ├── guards.py        #   What a route needs first; the only store access
│   ├── sse.py           #   Server-sent events, framed once
│   ├── estimates.py     #   What a run will cost, before it is paid for
│   ├── clients.py       #   Shared outbound clients, built on first use
│   ├── background.py    #   Fire-and-forget work, kept referenced
│   └── routes/          #   One module per resource, each register_*_routes
├── config/              # Settings: shape, loading, persistence
├── llm/                 # Everything that talks to a model
├── plex/                # Everything that talks to a Plex server
│   ├── connection.py    #   The handle, the retry loop, the reconnect
│   ├── library.py       #   Reads: tracks, albums, stats, search
│   ├── playlists.py     #   Writes: create, update, the scratch playlist
│   ├── playback.py      #   Clients and play queues
│   ├── filters.py       #   A query, as Plex expresses one
│   └── client.py        #   PlexClient, composing them, plus its store
├── library/             # The local mirror of the Plex library
│   ├── sync.py          #   Writes it, resumably
│   ├── tracks.py        #   Reads it
│   ├── albums.py        #   Reads it, aggregated per album
│   ├── filters.py       #   What to keep, as SQL
│   └── tables.py        #   The rows
├── recommender/         # The album recommendation pipeline
│   ├── models.py        #   Shapes every stage passes
│   ├── prompts.py       #   Every word sent to a model
│   ├── selection.py     #   What to ask, what to filter, what to pick
│   ├── facts.py         #   Research read into checkable facts
│   ├── pitches.py       #   Writing, fact-checking, rewriting
│   ├── sessions.py      #   The flow held between requests
│   ├── round.py         #   One generation round, end to end
│   └── pipeline.py      #   The facade, plus its store
├── research/            # External metadata, over four sources
│   ├── models.py        #   What each API answers, parsed once per shape
│   ├── http.py          #   The shared client and the rate limit
│   ├── safety.py        #   Whether a URL may be fetched, hop by hop
│   ├── musicbrainz.py   #   Finding the album, then reading it
│   ├── wikipedia.py     #   The article, minus what a pitch cannot use
│   ├── covers.py        #   Cover Art Archive front covers
│   ├── reviews.py       #   Critical reviews, read off whatever page is linked
│   └── album.py         #   AlbumResearch, the facade
├── results/             # Saved history of playlists and recommendations
├── db/                  # Engine, session, migrations
├── analyzer.py          # Prompt analysis + seed track dimensions
├── generator.py         # Playlist generation
├── matching.py          # Fuzzy name matching, shared
└── models.py            # HTTP request and response models

frontend/                # Vanilla HTML/CSS/JS, no build step
tests/                   # pytest, mirroring backend/ exactly
```

## Constitution principles

1. **Library-First**: All playlist tracks MUST exist in the user's library
2. **Simplicity**: No build steps, no frontend frameworks, single container
3. **User Agency**: Users control filters and can remove/regenerate
4. **Cost Transparency**: Display token counts and estimated costs
5. **Plexamp Aesthetic**: Dark theme (#1a1a1a), amber accent (#e5a00d)

## Key design decisions

- **Filter-first**: Apply genre/decade filters before sending to the LLM (handles 50k+ libraries)
- **Local SQLite cache** at `data/library_cache.db` mirrors Plex track metadata; genres are
  normalized into `track_genres` and kept in step by trigger, so filters use an index instead of
  scanning and parsing JSON per row
- **Resumable sync**: page offsets are checkpointed to `sync_state`; a failed sync keeps what it
  wrote and resumes rather than restarting
- **plexapi autoreload is disabled** (`PLEXAPI_PLEXAPI_AUTORELOAD=false`, set in
  `backend/plex/connection.py` before the import). Left on, a missing attribute triggers a full refetch
  per object and a large sync overloads the Plex server. `getattr(obj, x, default)` does not
  suppress it — plexapi sets missing attributes to `None`, so no `AttributeError` is raised
- **No auth**: relies on network security (home LAN, VPN, reverse proxy)
- **Album art proxy**: backend proxies art so the Plex token never reaches the browser; responses
  carry a long `Cache-Control` and an `ETag` derived from the thumb path
- **Tunables live on the config, not in the code**: anything that varies with a deployment — Plex
  page size and timeouts, fuzzy matching floors, round shape, research endpoints and caps, art
  cache lifetimes — is a `MediasageConfig` field reachable as `MEDIASAGE_<SECTION>__<FIELD>`. What
  stays a module constant is what varies with *this repository*: prompt text and the token
  estimates measured from it, protocol shapes, scoring weights, identifier widths
- **Two-model strategy**: smart model for analysis, cheap model for generation
- **Fuzzy track matching**: rapidfuzz (threshold ~60) to match LLM responses to the library
- **Live version filtering**: excludes tracks with "live", "concert", or dates in title/album

## Environment variables

Every setting is reachable as `MEDIASAGE_<SECTION>__<FIELD>`; sections nest with
a double underscore. Environment beats `.env`, which beats YAML.

```bash
MEDIASAGE_PLEX__URL=http://your-plex-server:32400
MEDIASAGE_PLEX__TOKEN=your-plex-token
MEDIASAGE_PLEX__MUSIC_LIBRARY=Music
MEDIASAGE_LLM__PROVIDER=anthropic  # Required; no default
MEDIASAGE_LLM__API_KEY=sk-ant-...  # One key, whichever provider is selected
MEDIASAGE_LLM__MODEL_ANALYSIS=claude-sonnet-4-5
MEDIASAGE_LLM__MODEL_GENERATION=claude-haiku-4-5
MEDIASAGE_LLM__CONTEXT_WINDOW=200000  # Required for every provider; no table
MEDIASAGE_LLM__ENDPOINT_URL=http://localhost:11434  # Local providers only

# Optional, with defaults. Set them when your deployment differs.
MEDIASAGE_LLM__REQUEST_TIMEOUT=600      # Seconds per call
MEDIASAGE_LLM__MAX_OUTPUT_TOKENS=8192   # Ceiling on one completion
MEDIASAGE_LLM__MAX_RETRIES=3            # Attempts, backed off exponentially
MEDIASAGE_LLM__PROBE_TIMEOUT=5          # Seconds for a liveness check

# Cost display. Per million tokens; unset means the UI reports no cost.
MEDIASAGE_LLM__COST_ANALYSIS_INPUT=3.00
MEDIASAGE_LLM__COST_ANALYSIS_OUTPUT=15.00
MEDIASAGE_LLM__COST_GENERATION_INPUT=1.00
MEDIASAGE_LLM__COST_GENERATION_OUTPUT=5.00

# Prompt budgeting. Averages per library line; tune for your naming.
MEDIASAGE_BUDGET__TOKENS_PER_TRACK=40
MEDIASAGE_BUDGET__TOKENS_PER_ALBUM=25
MEDIASAGE_BUDGET__CONTEXT_BUFFER_FRACTION=0.10
MEDIASAGE_BUDGET__RESERVED_PROMPT_TOKENS=1000

# Library cache. Sync behaviour and what counts as a live recording.
MEDIASAGE_LIBRARY__SYNC_BATCH_SIZE=500        # Rows per transaction and per checkpoint
MEDIASAGE_LIBRARY__STALE_AFTER_HOURS=24       # Age at which a re-sync is suggested
MEDIASAGE_LIBRARY__WELL_LOVED_AVG_PLAYS=3.0   # Plays per track marking an album well-loved
MEDIASAGE_LIBRARY__LIVE_KEYWORDS=["live","concert","sbd","bootleg"]  # JSON array; [] disables
MEDIASAGE_LIBRARY__DATED_TITLES_ARE_LIVE=true # Treat a dated title as a live recording

# Plex server. How hard to lean on it; a NAS wants smaller pages and longer waits.
MEDIASAGE_PLEX__PAGE_SIZE=1000            # Rows per bulk request
MEDIASAGE_PLEX__CONNECT_TIMEOUT=30        # Seconds one Plex request may take
MEDIASAGE_PLEX__RECONNECT_COOLDOWN=30     # Seconds before a dropped client retries
MEDIASAGE_PLEX__RETRY_BACKOFF=[1,3,8,20]  # JSON array; length is the retry count, [] disables

# Fuzzy matching floors, 0-100. Clean tags tolerate a high one; a library full
# of "(Remastered)" suffixes needs a lower one. Too low plays the wrong record.
MEDIASAGE_MATCHING__TRACK_THRESHOLD=60    # A track the model named, against the library
MEDIASAGE_MATCHING__ALBUM_ARTIST_MIN=70   # Picking a library album: artist half
MEDIASAGE_MATCHING__ALBUM_COMBINED_MIN=70 # Picking a library album: both halves averaged
MEDIASAGE_MATCHING__PITCH_ARTIST_MIN=80   # Attaching a pitch: artist half
MEDIASAGE_MATCHING__PITCH_ALBUM_MIN=60    # Attaching a pitch: album half

# Recommendation rounds and the sessions held between requests.
MEDIASAGE_RECOMMEND__SESSION_EXPIRY=1800     # Seconds an untouched session survives
MEDIASAGE_RECOMMEND__MAX_SESSIONS=100        # Held at once; the oldest are evicted
MEDIASAGE_RECOMMEND__RECENT_LIMIT=30         # Albums remembered per session
MEDIASAGE_RECOMMEND__QUESTION_COUNT=2        # Clarifying questions per round
MEDIASAGE_RECOMMEND__PICK_COUNT=3            # Albums shown: one primary, the rest secondary
MEDIASAGE_RECOMMEND__DISCOVERY_REQUEST=7     # Asked for in discovery; owned ones filtered after
MEDIASAGE_RECOMMEND__SMALL_POOL=10           # Below this the model is told the pool is thin
MEDIASAGE_RECOMMEND__MAX_EXCLUSION_ALBUMS=2500 # Owned albums listed in the discovery prompt
MEDIASAGE_RECOMMEND__GENRES_PER_LINE=3       # Genres per album line in the prompt

# External research. The three endpoints take a local mirror; the caps are how
# much of a source fits alongside the album list in one prompt.
MEDIASAGE_RESEARCH__REQUEST_TIMEOUT=10         # Seconds one research call may take
MEDIASAGE_RESEARCH__MUSICBRAINZ_URL=https://musicbrainz.org/ws/2
MEDIASAGE_RESEARCH__MUSICBRAINZ_INTERVAL=1.0   # Seconds between MusicBrainz calls
MEDIASAGE_RESEARCH__COVER_ART_URL=https://coverartarchive.org
MEDIASAGE_RESEARCH__WIKIPEDIA_API_URL=https://en.wikipedia.org/w/api.php
MEDIASAGE_RESEARCH__WIKIPEDIA_MAX_CHARS=8000   # Characters kept from one article
MEDIASAGE_RESEARCH__WIKIPEDIA_DROP_SECTIONS=["chart","personnel"]  # JSON array; [] keeps all
MEDIASAGE_RESEARCH__MAX_REVIEWS=2              # Reviews read per album; 0 disables
MEDIASAGE_RESEARCH__REVIEW_MAX_CHARS=2000      # Characters kept from one review
MEDIASAGE_RESEARCH__REVIEW_MIN_CHARS=1500      # Earliest sentence break accepted when trimming
MEDIASAGE_RESEARCH__BLOCKED_REVIEW_HOSTS=["allmusic.com"]  # Never fetched; JSON array
MEDIASAGE_RESEARCH__MAX_REDIRECTS=5            # Hops followed, each re-checked as safe

# Album art proxy. Plex art is content-addressed, so it may be cached hard.
MEDIASAGE_ART__TIMEOUT=10                  # Seconds an art fetch may take
MEDIASAGE_ART__CACHE_MAX_AGE=604800        # Seconds a browser may keep Plex art
MEDIASAGE_ART__EXTERNAL_CACHE_MAX_AGE=86400 # Seconds a browser may keep external art
MEDIASAGE_ART__EXTERNAL_DOMAINS=["coverartarchive.org","archive.org"]  # Allowlist; subdomains count
MEDIASAGE_ART__MAX_REDIRECTS=5             # Hops followed, each re-checked against the allowlist
```

## LLM providers

Every provider goes through LangChain's `init_chat_model`, so there is one code path and one
set of arguments. `backend/llm/constants.py` maps our provider names onto LangChain's:

| `MEDIASAGE_LLM__PROVIDER` | LangChain provider | Reached by |
|---|---|---|
| `anthropic` | `anthropic` | API key |
| `openai` | `openai` | API key |
| `gemini` | `google_genai` | API key |
| `ollama` | `ollama` | `endpoint_url` |
| `custom` | `openai` | `endpoint_url` + optional key |

`custom` covers any OpenAI-compatible server — MLX, LM Studio, OpenRouter, vLLM.

Model names, context windows and prices are **not** built into the code. There is no table of
per-model limits to go stale: `context_window` is required of every provider, and an unset price
means the UI reports no cost rather than a wrong one. Token counts shown after a call are the
ones the provider reported, not estimates.

`smart_generation: true` spends the analysis model on generation too (higher quality, more cost).

**Ollama** additionally exposes `/api/tags` and `/api/show` for model discovery and context-window
detection, via `backend/llm/ollama.py` on the official `ollama` SDK. LangChain has no equivalent,
so that one admin API is wrapped by hand.
