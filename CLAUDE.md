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
- Each package's `__init__.py` opens with a map of its modules. Read that before opening a file.

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

## No loose functions

**A module-level function is a defect unless it is genuinely necessary.** Behaviour belongs on the
model or the class that owns the data it works on. "It is short", "it is pure", and "it has no
state" are not reasons to leave one floating — a pure function that builds a `Foo` is
`Foo.of(...)`, and a pure function that answers a question about a `Foo` is a method or property
on `Foo`.

Before writing `def` at column zero, name the object it belongs to. If one exists, put it there.
If none exists, that usually means a model is missing, not that a function is warranted.

The genuinely necessary cases, and roughly all of them:

- A framework demands the shape: FastAPI route handlers, `register_*_routes`, pydantic
  `@field_validator`, SQLAlchemy event hooks.
- The function is the module's whole public surface and no type it touches is ours to extend —
  a converter between two third-party shapes.
- Putting it on the model would force that model to import a layer it must not know about.
- It builds prompt text in a `prompts.py`. Every word sent to a model stays in one file per
  package; spreading it across the models that send it is worse than the floating `def`.

When one of those applies, say which in the docstring. Everything else moves.

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

Which settings exist, what each defaults to, and what a default means live in
`backend/config/models.py`. Read it there; do not restate the list anywhere else.

## LLM providers

Every provider goes through LangChain's `init_chat_model`, so there is one code path and one
set of arguments. `backend/llm/constants.py` maps our provider names onto LangChain's:

`custom` covers any OpenAI-compatible server — MLX, LM Studio, OpenRouter, vLLM. Hosted
providers are reached by API key; `ollama` and `custom` by `endpoint_url`.

Model names, context windows and prices are **not** built into the code. There is no table of
per-model limits to go stale: `context_window` is required of every provider, and an unset price
means the UI reports no cost rather than a wrong one. Token counts shown after a call are the
ones the provider reported, not estimates.

`smart_generation: true` spends the analysis model on generation too (higher quality, more cost).

**Ollama** additionally exposes `/api/tags` and `/api/show` for model discovery and context-window
detection, via `backend/llm/ollama.py` on the official `ollama` SDK. LangChain has no equivalent,
so that one admin API is wrapped by hand.
